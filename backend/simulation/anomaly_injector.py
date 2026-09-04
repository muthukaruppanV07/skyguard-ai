import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.config import settings, ANOMALY_INJECTION_TYPES
from backend.models import Reading, Station
from backend.simulation.aws_simulator import AWSSimulator


class InjectedAnomaly:
    def __init__(
        self,
        station_id: str,
        fault_type: str,
        timestamp: datetime,
        original_value: float,
        faulty_value: float,
        parameter: str,
        duration_minutes: int = 0,
        metadata: Dict = None,
    ):
        self.station_id = station_id
        self.fault_type = fault_type
        self.timestamp = timestamp
        self.original_value = original_value
        self.faulty_value = faulty_value
        self.parameter = parameter
        self.duration_minutes = duration_minutes
        self.metadata = metadata or {}
        self.end_time = timestamp + timedelta(minutes=duration_minutes) if duration_minutes > 0 else timestamp


class AnomalyInjector:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.simulator = AWSSimulator(db)
        self.injected_anomalies: List[InjectedAnomaly] = []
        self.active_injections: Dict[str, InjectedAnomaly] = {}

    async def inject(
        self,
        station_id: str,
        fault_type: str,
        params: Dict = None,
    ) -> Dict[str, Any]:
        params = params or {}
        
        if fault_type not in ANOMALY_INJECTION_TYPES:
            raise ValueError(f"Unknown fault type: {fault_type}")

        current_time = datetime.utcnow()
        state = self.simulator.stations.get(station_id)
        if not state:
            raise ValueError(f"Station {station_id} not found")

        last_temp = state["last_temp"]
        last_pressure = state["last_pressure"]
        last_humidity = state["last_humidity"]

        if fault_type == "TEMPERATURE_SPIKE":
            spike_magnitude = params.get("magnitude", random.uniform(15, 30))
            faulty_temp = last_temp + spike_magnitude
            self.simulator.stations[station_id]["last_temp"] = faulty_temp
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=last_temp,
                faulty_value=faulty_temp,
                parameter="temperature",
                metadata={"magnitude": spike_magnitude},
            )
            self.injected_anomalies.append(anomaly)

        elif fault_type == "PRESSURE_SPIKE":
            spike_magnitude = params.get("magnitude", random.uniform(20, 50))
            faulty_pressure = last_pressure + spike_magnitude
            self.simulator.stations[station_id]["last_pressure"] = faulty_pressure
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=last_pressure,
                faulty_value=faulty_pressure,
                parameter="pressure",
                metadata={"magnitude": spike_magnitude},
            )
            self.injected_anomalies.append(anomaly)

        elif fault_type == "HUMIDITY_SPIKE":
            spike_magnitude = params.get("magnitude", random.uniform(30, 60))
            direction = params.get("direction", random.choice([-1, 1]))
            faulty_humidity = max(0, min(100, last_humidity + direction * spike_magnitude))
            self.simulator.stations[station_id]["last_humidity"] = faulty_humidity
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=last_humidity,
                faulty_value=faulty_humidity,
                parameter="humidity",
                metadata={"magnitude": spike_magnitude, "direction": direction},
            )
            self.injected_anomalies.append(anomaly)

        elif fault_type == "TEMPERATURE_DRIFT":
            drift_rate = params.get("rate", random.uniform(0.5, 2.0))
            duration = params.get("duration_minutes", 60)
            self.simulator.apply_drift(station_id, temp_drift=drift_rate)
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=last_temp,
                faulty_value=last_temp + drift_rate,
                parameter="temperature",
                duration_minutes=duration,
                metadata={"rate_per_hour": drift_rate, "duration_minutes": duration},
            )
            self.injected_anomalies.append(anomaly)
            self.active_injections[f"{station_id}_temp_drift"] = anomaly

        elif fault_type == "PRESSURE_DRIFT":
            drift_rate = params.get("rate", random.uniform(0.2, 1.0))
            duration = params.get("duration_minutes", 60)
            self.simulator.apply_drift(station_id, pressure_drift=drift_rate)
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=last_pressure,
                faulty_value=last_pressure + drift_rate,
                parameter="pressure",
                duration_minutes=duration,
                metadata={"rate_per_hour": drift_rate, "duration_minutes": duration},
            )
            self.injected_anomalies.append(anomaly)
            self.active_injections[f"{station_id}_pressure_drift"] = anomaly

        elif fault_type == "HUMIDITY_DRIFT":
            drift_rate = params.get("rate", random.uniform(1.0, 5.0))
            duration = params.get("duration_minutes", 60)
            self.simulator.apply_drift(station_id, humidity_drift=drift_rate)
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=last_humidity,
                faulty_value=last_humidity + drift_rate,
                parameter="humidity",
                duration_minutes=duration,
                metadata={"rate_per_hour": drift_rate, "duration_minutes": duration},
            )
            self.injected_anomalies.append(anomaly)
            self.active_injections[f"{station_id}_humidity_drift"] = anomaly

        elif fault_type == "FROZEN_SENSOR":
            sensor = params.get("sensor", random.choice(["temperature", "pressure", "humidity"]))
            duration = params.get("duration_minutes", 30)
            self.simulator.freeze_sensor(station_id, duration)
            
            frozen_val = {"temperature": last_temp, "pressure": last_pressure, "humidity": last_humidity}[sensor]
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=frozen_val,
                faulty_value=frozen_val,
                parameter=sensor,
                duration_minutes=duration,
                metadata={"sensor": sensor, "duration_minutes": duration},
            )
            self.injected_anomalies.append(anomaly)

        elif fault_type == "MISSING_OBSERVATIONS":
            duration = params.get("duration_minutes", 10)
            self.simulator.set_comm_failure(station_id, duration)
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=0,
                faulty_value=0,
                parameter="all",
                duration_minutes=duration,
                metadata={"duration_minutes": duration},
            )
            self.injected_anomalies.append(anomaly)

        elif fault_type == "DUPLICATE_OBSERVATIONS":
            count = params.get("count", 3)
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=0,
                faulty_value=0,
                parameter="all",
                metadata={"duplicate_count": count},
            )
            self.injected_anomalies.append(anomaly)

        elif fault_type == "COMMUNICATION_FAILURE":
            duration = params.get("duration_minutes", 15)
            self.simulator.set_comm_failure(station_id, duration)
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=0,
                faulty_value=0,
                parameter="all",
                duration_minutes=duration,
                metadata={"duration_minutes": duration},
            )
            self.injected_anomalies.append(anomaly)

        elif fault_type == "RANDOM_NOISE":
            factor = params.get("factor", 5.0)
            duration = params.get("duration_minutes", 10)
            self.simulator.set_degradation(station_id, factor)
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=0,
                faulty_value=0,
                parameter="all",
                duration_minutes=duration,
                metadata={"noise_factor": factor, "duration_minutes": duration},
            )
            self.injected_anomalies.append(anomaly)

        elif fault_type == "MULTIVARIATE_INCONSISTENCY":
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=last_temp,
                faulty_value=last_temp + 10,
                parameter="temperature",
                metadata={"description": "Temperature rises but humidity doesn't drop as expected"},
            )
            self.simulator.stations[station_id]["last_temp"] = last_temp + 10
            self.injected_anomalies.append(anomaly)

        elif fault_type == "SENSOR_DEGRADATION":
            factor = params.get("factor", 3.0)
            self.simulator.set_degradation(station_id, factor)
            
            anomaly = InjectedAnomaly(
                station_id=station_id,
                fault_type=fault_type,
                timestamp=current_time,
                original_value=0,
                faulty_value=0,
                parameter="all",
                metadata={"degradation_factor": factor},
            )
            self.injected_anomalies.append(anomaly)

        return {
            "status": "injected",
            "fault_type": fault_type,
            "station_id": station_id,
            "timestamp": current_time.isoformat(),
            "original_value": anomaly.original_value,
            "faulty_value": anomaly.faulty_value,
            "parameter": anomaly.parameter,
            "metadata": anomaly.metadata,
        }

    def get_ground_truth(self, station_id: str = None, since: datetime = None) -> List[Dict]:
        anomalies = self.injected_anomalies
        if station_id:
            anomalies = [a for a in anomalies if a.station_id == station_id]
        if since:
            anomalies = [a for a in anomalies if a.timestamp >= since]
        
        return [
            {
                "station_id": a.station_id,
                "fault_type": a.fault_type,
                "timestamp": a.timestamp.isoformat(),
                "original_value": a.original_value,
                "faulty_value": a.faulty_value,
                "parameter": a.parameter,
                "duration_minutes": a.duration_minutes,
                "metadata": a.metadata,
            }
            for a in anomalies
        ]

    def clear_history(self):
        self.injected_anomalies.clear()
        self.active_injections.clear()


class DemoScenario:
    def __init__(self, injector: AnomalyInjector):
        self.injector = injector

    async def run_full_demo(self):
        await self.injector.inject("AWS001", "TEMPERATURE_SPIKE", {"magnitude": 25})
        await asyncio.sleep(2)
        
        await self.injector.inject("AWS002", "TEMPERATURE_DRIFT", {"rate": 1.5, "duration_minutes": 30})
        await asyncio.sleep(2)
        
        await self.injector.inject("AWS003", "FROZEN_SENSOR", {"sensor": "humidity", "duration_minutes": 20})
        await asyncio.sleep(2)
        
        await self.injector.inject("AWS004", "COMMUNICATION_FAILURE", {"duration_minutes": 10})
        await asyncio.sleep(2)
        
        await self.injector.inject("AWS005", "MULTIVARIATE_INCONSISTENCY", {})
        await asyncio.sleep(2)
        
        await self.injector.inject("AWS006", "PRESSURE_SPIKE", {"magnitude": 35})
        await asyncio.sleep(2)
        
        await self.injector.inject("AWS007", "HUMIDITY_SPIKE", {"magnitude": 40, "direction": -1})
        await asyncio.sleep(2)
        
        await self.injector.inject("AWS008", "SENSOR_DEGRADATION", {"factor": 4.0})

    async def reset_demo(self):
        for station_id in self.injector.simulator.stations:
            self.injector.simulator.unfreeze_sensor(station_id)
            self.injector.simulator.clear_comm_failure(station_id)
            self.injector.simulator.apply_drift(station_id, 0, 0, 0)
            self.injector.simulator.set_degradation(station_id, 1.0)
        self.injector.clear_history()


import asyncio