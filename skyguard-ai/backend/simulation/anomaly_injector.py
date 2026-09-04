import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import random
import json

from backend.config import settings
from backend.simulation.aws_simulator import WeatherState, AWSSimulator


class FaultType(str, Enum):
    TEMPERATURE_SPIKE = "TEMPERATURE_SPIKE"
    TEMPERATURE_DRIFT = "TEMPERATURE_DRIFT"
    PRESSURE_SPIKE = "PRESSURE_SPIKE"
    PRESSURE_DRIFT = "PRESSURE_DRIFT"
    HUMIDITY_SPIKE = "HUMIDITY_SPIKE"
    HUMIDITY_DRIFT = "HUMIDITY_DRIFT"
    FROZEN_SENSOR = "FROZEN_SENSOR"
    MISSING_DATA = "MISSING_DATA"
    DUPLICATE_DATA = "DUPLICATE_DATA"
    RANDOM_NOISE = "RANDOM_NOISE"
    MULTIVARIATE_INCONSISTENCY = "MULTIVARIATE_INCONSISTENCY"
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"
    SENSOR_DEGRADATION = "SENSOR_DEGRADATION"


@dataclass
class InjectedAnomaly:
    station_id: str
    timestamp: datetime
    fault_type: FaultType
    parameter: str
    original_value: float
    injected_value: float
    description: str


class AnomalyInjector:
    def __init__(self, simulator: AWSSimulator, seed: Optional[int] = None):
        self.simulator = simulator
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

        self.injection_log: List[InjectedAnomaly] = []
        self.active_drifts: Dict[str, Dict] = {}
        self.active_degradations: Dict[str, Dict] = {}
        self.frozen_states: Dict[str, float] = {}
        self.communication_failure_until: Dict[str, datetime] = {}

    def inject_temperature_spike(self, timestamp: datetime, magnitude: Optional[float] = None) -> InjectedAnomaly:
        if magnitude is None:
            magnitude = np.random.uniform(15, 30)

        original = self.simulator.last_state.temperature if self.simulator.last_state else 25.0
        sign = 1 if np.random.random() > 0.5 else -1
        injected = original + sign * magnitude

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.TEMPERATURE_SPIKE,
            parameter="temperature",
            original_value=original,
            injected_value=injected,
            description=f"Temperature spike of {sign * magnitude:.1f}°C injected"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_temperature_drift(self, timestamp: datetime, rate: Optional[float] = None, duration_minutes: int = 60) -> InjectedAnomaly:
        if rate is None:
            rate = np.random.uniform(0.5, 2.0)

        original = self.simulator.last_state.temperature if self.simulator.last_state else 25.0
        injected = original + rate

        self.active_drifts["temperature"] = {
            "rate": rate,
            "start_time": timestamp,
            "duration_minutes": duration_minutes,
            "accumulated": rate
        }

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.TEMPERATURE_DRIFT,
            parameter="temperature",
            original_value=original,
            injected_value=injected,
            description=f"Temperature drift started at {rate:.2f}°C per reading"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_pressure_spike(self, timestamp: datetime, magnitude: Optional[float] = None) -> InjectedAnomaly:
        if magnitude is None:
            magnitude = np.random.uniform(10, 30)

        original = self.simulator.last_state.pressure if self.simulator.last_state else 1013.25
        sign = 1 if np.random.random() > 0.5 else -1
        injected = original + sign * magnitude

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.PRESSURE_SPIKE,
            parameter="pressure",
            original_value=original,
            injected_value=injected,
            description=f"Pressure spike of {sign * magnitude:.1f} hPa injected"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_humidity_spike(self, timestamp: datetime, magnitude: Optional[float] = None) -> InjectedAnomaly:
        if magnitude is None:
            magnitude = np.random.uniform(20, 50)

        original = self.simulator.last_state.humidity if self.simulator.last_state else 60.0
        sign = 1 if np.random.random() > 0.5 else -1
        injected = np.clip(original + sign * magnitude, 0, 100)

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.HUMIDITY_SPIKE,
            parameter="humidity",
            original_value=original,
            injected_value=injected,
            description=f"Humidity spike of {sign * magnitude:.1f}% injected"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_frozen_sensor(self, timestamp: datetime, parameter: str = "temperature", duration_minutes: int = 30) -> InjectedAnomaly:
        if self.simulator.last_state is None:
            return None

        if parameter == "temperature":
            frozen_value = self.simulator.last_state.temperature
        elif parameter == "pressure":
            frozen_value = self.simulator.last_state.pressure
        elif parameter == "humidity":
            frozen_value = self.simulator.last_state.humidity
        else:
            return None

        self.frozen_states[parameter] = {
            "value": frozen_value,
            "start_time": timestamp,
            "duration_minutes": duration_minutes
        }

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.FROZEN_SENSOR,
            parameter=parameter,
            original_value=frozen_value,
            injected_value=frozen_value,
            description=f"{parameter.capitalize()} sensor frozen at {frozen_value:.2f} for {duration_minutes} minutes"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_missing_data(self, timestamp: datetime, gap_minutes: int = 30) -> InjectedAnomaly:
        self.communication_failure_until[self.simulator.station_id] = timestamp + timedelta(minutes=gap_minutes)

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.MISSING_DATA,
            parameter="all",
            original_value=0.0,
            injected_value=0.0,
            description=f"Communication failure - missing data for {gap_minutes} minutes"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_duplicate_data(self, timestamp: datetime, count: int = 3) -> List[InjectedAnomaly]:
        anomalies = []
        if self.simulator.last_state is None:
            return anomalies

        for i in range(count):
            dup_time = timestamp + timedelta(minutes=i * 5)
            anomaly = InjectedAnomaly(
                station_id=self.simulator.station_id,
                timestamp=dup_time,
                fault_type=FaultType.DUPLICATE_DATA,
                parameter="all",
                original_value=self.simulator.last_state.temperature,
                injected_value=self.simulator.last_state.temperature,
                description=f"Duplicate reading #{i+1} injected"
            )
            anomalies.append(anomaly)
            self.injection_log.append(anomaly)
        return anomalies

    def inject_random_noise(self, timestamp: datetime, parameter: str = "temperature", noise_factor: float = 5.0) -> InjectedAnomaly:
        if self.simulator.last_state is None:
            return None

        if parameter == "temperature":
            original = self.simulator.last_state.temperature
            injected = original + np.random.normal(0, noise_factor)
        elif parameter == "pressure":
            original = self.simulator.last_state.pressure
            injected = original + np.random.normal(0, noise_factor)
        elif parameter == "humidity":
            original = self.simulator.last_state.humidity
            injected = np.clip(original + np.random.normal(0, noise_factor), 0, 100)
        else:
            return None

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.RANDOM_NOISE,
            parameter=parameter,
            original_value=original,
            injected_value=injected,
            description=f"Random noise injected into {parameter}"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_multivariate_inconsistency(self, timestamp: datetime) -> InjectedAnomaly:
        if self.simulator.last_state is None:
            return None

        original_temp = self.simulator.last_state.temperature
        original_humidity = self.simulator.last_state.humidity
        original_pressure = self.simulator.last_state.pressure

        inconsistency_type = np.random.choice(["temp_humidity", "temp_pressure", "pressure_humidity"])

        if inconsistency_type == "temp_humidity":
            injected_temp = original_temp + np.random.uniform(10, 20)
            injected_humidity = np.clip(original_humidity - np.random.uniform(20, 40), 0, 100)
            injected_pressure = original_pressure
            param = "temperature,humidity"
        elif inconsistency_type == "temp_pressure":
            injected_temp = original_temp + np.random.uniform(10, 15)
            injected_pressure = original_pressure + np.random.uniform(15, 30)
            injected_humidity = original_humidity
            param = "temperature,pressure"
        else:
            injected_pressure = original_pressure + np.random.uniform(15, 25)
            injected_humidity = np.clip(original_humidity + np.random.uniform(15, 30), 0, 100)
            injected_temp = original_temp
            param = "pressure,humidity"

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.MULTIVARIATE_INCONSISTENCY,
            parameter=param,
            original_value=original_temp,
            injected_value=injected_temp,
            description=f"Multivariate inconsistency: {inconsistency_type} - physically implausible combination"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_communication_failure(self, timestamp: datetime, duration_minutes: int = 20) -> InjectedAnomaly:
        self.communication_failure_until[self.simulator.station_id] = timestamp + timedelta(minutes=duration_minutes)

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.COMMUNICATION_FAILURE,
            parameter="all",
            original_value=0.0,
            injected_value=0.0,
            description=f"Communication failure for {duration_minutes} minutes"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def inject_sensor_degradation(self, timestamp: datetime, parameter: str = "humidity", degradation_rate: float = 0.1) -> InjectedAnomaly:
        self.active_degradations[parameter] = {
            "rate": degradation_rate,
            "start_time": timestamp,
            "accumulated_error": 0.0
        }

        anomaly = InjectedAnomaly(
            station_id=self.simulator.station_id,
            timestamp=timestamp,
            fault_type=FaultType.SENSOR_DEGRADATION,
            parameter=parameter,
            original_value=0.0,
            injected_value=0.0,
            description=f"{parameter.capitalize()} sensor degradation started (rate: {degradation_rate} per reading)"
        )
        self.injection_log.append(anomaly)
        return anomaly

    def apply_active_effects(self, timestamp: datetime, normal_state: WeatherState) -> WeatherState:
        temp = normal_state.temperature
        pressure = normal_state.pressure
        humidity = normal_state.humidity

        if "temperature" in self.active_drifts:
            drift = self.active_drifts["temperature"]
            elapsed = (timestamp - drift["start_time"]).total_seconds() / 60
            if elapsed <= drift["duration_minutes"]:
                temp += drift["rate"]
                drift["accumulated"] += drift["rate"]
            else:
                del self.active_drifts["temperature"]

        if "temperature" in self.frozen_states:
            frozen = self.frozen_states["temperature"]
            elapsed = (timestamp - frozen["start_time"]).total_seconds() / 60
            if elapsed <= frozen["duration_minutes"]:
                temp = frozen["value"]
            else:
                del self.frozen_states["temperature"]

        if "pressure" in self.frozen_states:
            frozen = self.frozen_states["pressure"]
            elapsed = (timestamp - frozen["start_time"]).total_seconds() / 60
            if elapsed <= frozen["duration_minutes"]:
                pressure = frozen["value"]
            else:
                del self.frozen_states["pressure"]

        if "humidity" in self.frozen_states:
            frozen = self.frozen_states["humidity"]
            elapsed = (timestamp - frozen["start_time"]).total_seconds() / 60
            if elapsed <= frozen["duration_minutes"]:
                humidity = frozen["value"]
            else:
                del self.frozen_states["humidity"]

        for param, deg in self.active_degradations.items():
            deg["accumulated_error"] += deg["rate"]
            if param == "temperature":
                temp += deg["accumulated_error"] + np.random.normal(0, deg["rate"] * 2)
            elif param == "pressure":
                pressure += deg["accumulated_error"] + np.random.normal(0, deg["rate"] * 2)
            elif param == "humidity":
                humidity += deg["accumulated_error"] + np.random.normal(0, deg["rate"] * 2)
                humidity = np.clip(humidity, 0, 100)

        return WeatherState(
            temperature=round(temp, 2),
            pressure=round(pressure, 2),
            humidity=round(humidity, 2),
            timestamp=timestamp
        )

    def is_communication_failed(self, station_id: str, timestamp: datetime) -> bool:
        if station_id in self.communication_failure_until:
            if timestamp < self.communication_failure_until[station_id]:
                return True
            else:
                del self.communication_failure_until[station_id]
        return False

    def get_injection_log(self) -> List[InjectedAnomaly]:
        return self.injection_log.copy()

    def clear_log(self):
        self.injection_log.clear()
        self.active_drifts.clear()
        self.active_degradations.clear()
        self.frozen_states.clear()
        self.communication_failure_until.clear()


class MultiStationAnomalyInjector:
    def __init__(self, multi_simulator, seed: Optional[int] = None):
        self.injectors: Dict[str, AnomalyInjector] = {}
        for station_id, simulator in multi_simulator.simulators.items():
            sim_seed = seed + hash(station_id) % 1000 if seed is not None else None
            self.injectors[station_id] = AnomalyInjector(simulator, sim_seed)

    def get_injector(self, station_id: str) -> Optional[AnomalyInjector]:
        return self.injectors.get(station_id)

    def inject_anomaly(self, station_id: str, fault_type: FaultType, timestamp: Optional[datetime] = None, **kwargs) -> Optional[InjectedAnomaly]:
        if timestamp is None:
            timestamp = datetime.utcnow()

        injector = self.injectors.get(station_id)
        if not injector:
            return None

        method_map = {
            FaultType.TEMPERATURE_SPIKE: injector.inject_temperature_spike,
            FaultType.TEMPERATURE_DRIFT: injector.inject_temperature_drift,
            FaultType.PRESSURE_SPIKE: injector.inject_pressure_spike,
            FaultType.HUMIDITY_SPIKE: injector.inject_humidity_spike,
            FaultType.FROZEN_SENSOR: injector.inject_frozen_sensor,
            FaultType.MISSING_DATA: injector.inject_missing_data,
            FaultType.DUPLICATE_DATA: injector.inject_duplicate_data,
            FaultType.RANDOM_NOISE: injector.inject_random_noise,
            FaultType.MULTIVARIATE_INCONSISTENCY: injector.inject_multivariate_inconsistency,
            FaultType.COMMUNICATION_FAILURE: injector.inject_communication_failure,
            FaultType.SENSOR_DEGRADATION: injector.inject_sensor_degradation,
        }

        method = method_map.get(fault_type)
        if method:
            return method(timestamp, **kwargs)
        return None

    def apply_all_active_effects(self, timestamp: datetime, normal_states: Dict[str, WeatherState]) -> Dict[str, WeatherState]:
        result = {}
        for station_id, injector in self.injectors.items():
            if station_id in normal_states:
                result[station_id] = injector.apply_active_effects(timestamp, normal_states[station_id])
            else:
                result[station_id] = normal_states[station_id]
        return result

    def get_all_logs(self) -> Dict[str, List[InjectedAnomaly]]:
        return {sid: inj.get_injection_log() for sid, inj in self.injectors.items()}

    def clear_all_logs(self):
        for injector in self.injectors.values():
            injector.clear_log()