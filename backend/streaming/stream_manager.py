import asyncio
import json
import time
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from enum import Enum
from typing import AsyncGenerator
import uuid
from collections import defaultdict


class StreamEventType(Enum):
    SENSOR_READING = "sensor_reading"
    ANOMALY_DETECTED = "anomaly_detected"
    MODEL_PREDICTION = "model_prediction"
    ALERT_TRIGGERED = "alert_triggered"
    SYSTEM_HEALTH = "system_health"
    MODEL_DRIFT = "model_drift"


@dataclass
class StreamEvent:
    event_id: str
    event_type: StreamEventType
    timestamp: datetime
    station_id: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorReadingEvent(StreamEvent):
    temperature: float = 0.0
    pressure: float = 0.0
    humidity: float = 0.0
    anomaly_score: float = 0.0
    severity: str = "NORMAL"


class RedisStreamManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_name: str = "skyguard:events",
        consumer_group: str = "skyguard:consumers",
        max_stream_length: int = 100000
    ):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.max_stream_length = max_stream_length
        self.redis_client = None
        self.consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.consumers: Dict[str, Callable] = {}
        self._background_tasks = []
    
    async def connect(self):
        self.redis_client = redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        try:
            await self.redis_client.xgroup_create(
                self.stream_name,
                self.consumer_group,
                id="0",
                mkstream=True
            )
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
        
        print(f"Connected to Redis stream: {self.stream_name}")
    
    async def disconnect(self):
        self.running = False
        for task in self._background_tasks:
            task.cancel()
        if self.redis_client:
            await self.redis_client.close()
    
    async def publish_event(self, event: StreamEvent) -> str:
        event_data = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "station_id": event.station_id,
            "payload": json.dumps(event.payload),
            "metadata": json.dumps(event.metadata)
        }
        
        event_id = await self.redis_client.xadd(
            self.stream_name,
            event_data,
            maxlen=self.max_stream_length,
            approximate=True
        )
        return event_id
    
    async def publish_batch(self, events: List[StreamEvent]) -> List[str]:
        pipe = self.redis_client.pipeline()
        event_ids = []
        
        for event in events:
            event_data = {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "station_id": event.station_id,
                "payload": json.dumps(event.payload),
                "metadata": json.dumps(event.metadata)
            }
            event_id = await self.redis_client.xadd(
                self.stream_name,
                event_data,
                maxlen=self.max_stream_length,
                approximate=True
            )
            event_ids.append(event_id)
        
        await pipe.execute()
        return event_ids
    
    def register_consumer(self, event_type: StreamEventType, callback: Callable):
        self.consumers[event_type] = callback
    
    async def start_consuming(self):
        self.running = True
        for event_type in StreamEventType:
            if event_type in self.consumers:
                task = asyncio.create_task(self._consume_stream(event_type))
                self._background_tasks.append(task)
    
    async def _consume_stream(self, event_type: StreamEventType):
        callback = self.consumers.get(event_type)
        if not callback:
            return
        
        while self.running:
            try:
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count=10,
                    block=5000
                )
                
                for stream, messages in messages:
                    for msg_id, data in messages:
                        try:
                            event = self._parse_event(data)
                            if event.event_type == event_type:
                                await callback(event)
                            await self.redis_client.xack(self.stream_name, self.consumer_group, msg_id)
                        except Exception as e:
                            print(f"Error processing message {msg_id}: {e}")
                            await self.redis_client.xack(self.stream_name, self.consumer_group, msg_id)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in consumer for {event_type}: {e}")
                await asyncio.sleep(1)
    
    def _parse_event(self, data: Dict) -> StreamEvent:
        return StreamEvent(
            event_id=data["event_id"],
            event_type=StreamEventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            station_id=data["station_id"],
            payload=json.loads(data["payload"]),
            metadata=json.loads(data.get("metadata", "{}"))
        )
    
    async def get_stream_info(self) -> Dict[str, Any]:
        info = await self.redis_client.xinfo_stream(self.stream_name)
        return {
            "stream_name": self.stream_name,
            "length": info["length"],
            "first_entry": info["first-entry"],
            "last_entry": info["last-entry"],
            "consumer_groups": len(info.get("groups", []))
        }
    
    async def get_pending_messages(self) -> List[Dict]:
        return await self.redis_client.xpending_range(
            self.stream_name,
            self.consumer_group,
            "-",
            "+",
            100
        )


class InMemoryStreamManager:
    def __init__(self):
        self.queues: Dict[StreamEventType, asyncio.Queue] = {
            event_type: asyncio.Queue() for event_type in StreamEventType
        }
        self.subscribers: Dict[StreamEventType, List[Callable]] = defaultdict(list)
        self.event_history: List[StreamEvent] = []
        self.max_history = 10000
        self.running = False
    
    async def publish_event(self, event: StreamEvent) -> str:
        event_id = str(uuid.uuid4())
        event.event_id = event_id
        
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
        
        queue = self.queues[event.event_type]
        await queue.put(event)
        
        for callback in self.subscribers[event.event_type]:
            try:
                await callback(event)
            except Exception as e:
                print(f"Error in subscriber callback: {e}")
        
        return event_id
    
    def subscribe(self, event_type: StreamEventType, callback: Callable):
        self.subscribers[event_type].append(callback)
    
    async def get_events(
        self, 
        event_type: StreamEventType, 
        since: datetime = None,
        limit: int = 100
    ) -> List[StreamEvent]:
        filtered = [
            e for e in self.event_history
            if e.event_type == event_type and (since is None or e.timestamp >= since)
        ]
        return filtered[-limit:]
    
    async def get_latest_event(self, event_type: StreamEventType) -> Optional[StreamEvent]:
        for event in reversed(self.event_history):
            if event.event_type == event_type:
                return event
        return None
    
    def get_event_counts(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for event in self.event_history:
            counts[event.event_type.value] += 1
        return dict(counts)


class StreamProcessor:
    def __init__(self, stream_manager):
        self.stream_manager = stream_manager
        self.processors: Dict[StreamEventType, List[Callable]] = defaultdict(list)
        self.running = False
        self._tasks = []
    
    def add_processor(self, event_type: StreamEventType, processor: Callable):
        self.processors[event_type].append(processor)
    
    async def start(self):
        self.running = True
        for event_type, processors in self.processors.items():
            if processors:
                self.stream_manager.subscribe(event_type, self._process_event)
        await self.stream_manager.start_consuming()
    
    async def _process_event(self, event: StreamEvent):
        for processor in self.processors.get(event.event_type, []):
            try:
                await processor(event)
            except Exception as e:
                print(f"Error in processor for {event.event_type}: {e}")
    
    async def stop(self):
        self.running = False
        for task in self._tasks:
            task.cancel()


class EventAggregator:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self.buffers: Dict[str, List[StreamEvent]] = defaultdict(list)
        self.aggregated_results: Dict[str, Any] = {}
        self.last_flush = datetime.utcnow()
    
    def add_event(self, event: StreamEvent):
        key = f"{event.station_id}:{event.event_type.value}"
        self.buffers[key].append(event)
    
    def flush(self) -> Dict[str, Any]:
        results = {}
        now = datetime.utcnow()
        
        for key, events in self.buffers.items():
            if not events:
                continue
            
            cutoff = now - timedelta(seconds=self.window_seconds)
            recent_events = [e for e in events if e.timestamp >= cutoff]
            
            if not recent_events:
                continue
            
            station_id, event_type = key.split(":", 1)
            
            if event_type == StreamEventType.SENSOR_READING.value:
                results[key] = self._aggregate_sensor_readings(recent_events)
            elif event_type == StreamEventType.ANOMALY_DETECTED.value:
                results[key] = self._aggregate_anomalies(recent_events)
            elif event_type == StreamEventType.MODEL_PREDICTION.value:
                results[key] = self._aggregate_predictions(recent_events)
            
            self.buffers[key] = [e for e in events if e.timestamp > cutoff]
        
        self.last_flush = now
        self.aggregated_results = results
        return results
    
    def _aggregate_sensor_readings(self, events: List[StreamEvent]) -> Dict:
        temps = [e.payload.get("temperature", 0) for e in events]
        pressures = [e.payload.get("pressure", 0) for e in events]
        humidities = [e.payload.get("humidity", 0) for e in events]
        scores = [e.payload.get("anomaly_score", 0) for e in events]
        
        return {
            "event_type": "sensor_reading_aggregated",
            "count": len(events),
            "temperature": {"mean": np.mean(temps), "min": np.min(temps), "max": np.max(temps), "std": np.std(temps)},
            "pressure": {"mean": np.mean(pressures), "min": np.min(pressures), "max": np.max(pressures), "std": np.std(pressures)},
            "humidity": {"mean": np.mean(humidities), "min": np.min(humidities), "max": np.max(humidities), "std": np.std(humidities)},
            "anomaly_score": {"mean": np.mean(scores), "max": np.max(scores)},
            "window_seconds": self.window_seconds,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _aggregate_anomalies(self, events: List[StreamEvent]) -> Dict:
        severities = [e.payload.get("severity", "NORMAL") for e in events]
        root_causes = [e.payload.get("root_cause", "UNKNOWN") for e in events]
        
        return {
            "event_type": "anomaly_aggregated",
            "count": len(events),
            "severity_distribution": {s: severities.count(s) for s in set(severities)},
            "root_cause_distribution": {c: root_causes.count(c) for c in set(root_causes)},
            "max_score": max([e.payload.get("anomaly_score", 0) for e in events]),
            "window_seconds": self.window_seconds,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _aggregate_predictions(self, events: List[StreamEvent]) -> Dict:
        predictions = [e.payload.get("prediction", 0) for e in events]
        scores = [e.payload.get("score", 0) for e in events]
        
        return {
            "event_type": "prediction_aggregated",
            "count": len(events),
            "prediction_distribution": {p: predictions.count(p) for p in set(predictions)},
            "avg_score": np.mean(scores),
            "max_score": np.max(scores),
            "window_seconds": self.window_seconds,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_aggregated_results(self) -> Dict[str, Any]:
        return self.aggregated_results


from dataclasses import field
import numpy as np