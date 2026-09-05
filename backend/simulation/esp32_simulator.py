import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import paho.mqtt.client as mqtt
from backend.config import settings
from backend.simulation.aws_simulator import AWSSimulator


class ESP32Status(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    CALIBRATING = "calibrating"


@dataclass
class ESP32SensorData:
    device_id: str
    timestamp: str
    temperature: float
    pressure: float
    humidity: float
    battery_voltage: float
    signal_strength: int
    status: str
    firmware_version: str = "1.0.0"


@dataclass
class ESP32Config:
    device_id: str
    station_id: str
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "aws/sensor/data"
    publish_interval: int = 5
    firmware_version: str = "1.0.0"


class ESP32Simulator:
    def __init__(self, config: ESP32Config):
        self.config = config
        self.aws_simulator = AWSSimulator(None)
        self.aws_simulator._init_station_states()
        
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        
        self.status = ESP32Status.OFFLINE
        self.running = False
        self.publish_task: Optional[asyncio.Task] = None
        self.battery_voltage = 4.2
        self.signal_strength = -45
        self.error_count = 0
        
        self._callbacks: Dict[str, List[Callable]] = {
            'data': [],
            'status_change': [],
            'error': []
        }

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.status = ESP32Status.ONLINE
            print(f"ESP32 {self.config.device_id} connected to MQTT broker")
            self._trigger_callback('status_change', self.status)
        else:
            self.status = ESP32Status.ERROR
            print(f"ESP32 {self.config.device_id} failed to connect: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.status = ESP32Status.OFFLINE
        print(f"ESP32 {self.config.device_id} disconnected from MQTT broker")
        self._trigger_callback('status_change', self.status)

    def _on_publish(self, client, userdata, mid):
        pass

    def register_callback(self, event: str, callback: Callable):
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _trigger_callback(self, event: str, data):
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Callback error: {e}")

    async def connect(self):
        try:
            self.client.connect(self.config.mqtt_broker, self.config.mqtt_port, 60)
            self.client.loop_start()
            await asyncio.sleep(1)
        except Exception as e:
            self.status = ESP32Status.ERROR
            self._trigger_callback('error', str(e))
            raise

    async def disconnect(self):
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()
        self.status = ESP32Status.OFFLINE
        self._trigger_callback('status_change', self.status)

    def _generate_sensor_data(self) -> ESP32SensorData:
        station_state = self.aws_simulator.stations.get(self.config.station_id, {})
        
        temp = station_state.get('last_temp', 25.0) + random.gauss(0, 0.1)
        pressure = station_state.get('last_pressure', 1013.25) + random.gauss(0, 0.05)
        humidity = station_state.get('last_humidity', 60.0) + random.gauss(0, 0.3)
        humidity = max(0, min(100, humidity))
        
        self.battery_voltage = max(3.0, self.battery_voltage - random.uniform(0.0001, 0.001))
        self.signal_strength = random.randint(-80, -30)
        
        return ESP32SensorData(
            device_id=self.config.device_id,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            temperature=round(temp, 2),
            pressure=round(pressure, 2),
            humidity=round(humidity, 2),
            battery_voltage=round(self.battery_voltage, 2),
            signal_strength=self.signal_strength,
            status=self.status.value,
            firmware_version=self.config.firmware_version
        )

    def inject_anomaly(self, anomaly_type: str, **params):
        if anomaly_type == "battery_low":
            self.battery_voltage = 3.1
        elif anomaly_type == "signal_lost":
            self.signal_strength = -95
        elif anomaly_type == "sensor_fault":
            self.error_count += 1
        elif anomaly_type == "temperature_spike":
            self.aws_simulator.stations[self.config.station_id]['last_temp'] += 20
        elif anomaly_type == "freeze":
            self.aws_simulator.freeze_sensor(self.config.station_id, params.get('duration', 30))

    async def start_publishing(self):
        self.running = True
        while self.running:
            try:
                data = self._generate_sensor_data()
                payload = json.dumps(asdict(data))
                
                result = self.client.publish(
                    self.config.mqtt_topic,
                    payload,
                    qos=1
                )
                
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    self.error_count += 1
                    self._trigger_callback('error', f"Publish failed: {result.rc}")
                else:
                    self._trigger_callback('data', data)
                
                await asyncio.sleep(self.config.publish_interval)
            except Exception as e:
                self.error_count += 1
                self._trigger_callback('error', str(e))
                await asyncio.sleep(5)

    def get_status(self) -> Dict:
        return {
            "device_id": self.config.device_id,
            "station_id": self.config.station_id,
            "status": self.status.value,
            "battery_voltage": self.battery_voltage,
            "signal_strength": self.signal_strength,
            "error_count": self.error_count,
            "uptime": time.time() - getattr(self, '_start_time', time.time()),
            "firmware_version": self.config.firmware_version
        }


class ESP32Fleet:
    def __init__(self, mqtt_broker: str = "localhost", mqtt_port: int = 1883):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.devices: Dict[str, ESP32Simulator] = {}
        self.running = False

    def add_device(self, device_id: str, station_id: str) -> ESP32Simulator:
        config = ESP32Config(
            device_id=device_id,
            station_id=station_id,
            mqtt_broker=self.mqtt_broker,
            mqtt_port=self.mqtt_port
        )
        device = ESP32Simulator(config)
        self.devices[device_id] = device
        return device

    async def connect_all(self):
        for device in self.devices.values():
            await device.connect()

    async def start_all(self):
        for device in self.devices.values():
            device.running = True
            asyncio.create_task(device.start_publishing())

    async def stop_all(self):
        for device in self.devices.values():
            await device.disconnect()

    def inject_fleet_anomaly(self, anomaly_type: str, device_ids: List[str] = None, **params):
        target_ids = device_ids or list(self.devices.keys())
        for device_id in target_ids:
            if device_id in self.devices:
                self.devices[device_id].inject_anomaly(anomaly_type, **params)

    def get_fleet_status(self) -> List[Dict]:
        return [device.get_status() for device in self.devices.values()]


async def run_esp32_demo():
    fleet = ESP32Fleet()
    
    stations = ["AWS001", "AWS002", "AWS003", "AWS004"]
    for i, station in enumerate(stations):
        device_id = f"ESP32-{i+1:03d}"
        fleet.add_device(device_id, station)
    
    await fleet.connect_all()
    await fleet.start_all()
    
    print("ESP32 Fleet started. Press Ctrl+C to stop.")
    
    try:
        while True:
            await asyncio.sleep(10)
            status = fleet.get_fleet_status()
            print(f"Fleet Status: {json.dumps(status, indent=2)}")
    except KeyboardInterrupt:
        print("Stopping fleet...")
        await fleet.stop_all()


import json