import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from backend.config import settings
from backend.simulation.aws_simulator import WeatherState


class ValidationFlag(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass
class ValidationResult:
    flag: ValidationFlag
    parameter: str
    message: str
    value: float
    expected_range: Tuple[float, float]
    severity: float  # 0-100


class DataValidator:
    def __init__(self):
        self.temp_min = settings.TEMP_MIN
        self.temp_max = settings.TEMP_MAX
        self.humidity_min = settings.HUMIDITY_MIN
        self.humidity_max = settings.HUMIDITY_MAX
        self.pressure_min = settings.PRESSURE_MIN
        self.pressure_max = settings.PRESSURE_MAX
        self.max_temp_rate = settings.MAX_TEMP_RATE
        self.max_humidity_rate = settings.MAX_HUMIDITY_RATE
        self.max_pressure_rate = settings.MAX_PRESSURE_RATE
        self.frozen_threshold = settings.FROZEN_THRESHOLD_MINUTES
        self.frozen_tolerance = settings.FROZEN_TOLERANCE

        self.station_history: Dict[str, List[WeatherState]] = {}
        self.max_history = 500

    def validate_reading(self, station_id: str, reading: WeatherState,
                         prev_reading: Optional[WeatherState] = None) -> List[ValidationResult]:
        results = []

        results.extend(self._validate_ranges(reading))
        results.extend(self._validate_rate_of_change(station_id, reading, prev_reading))
        results.extend(self._validate_frozen_sensor(station_id, reading))
        results.extend(self._validate_multivariate_consistency(reading))
        results.extend(self._validate_timestamp(reading))

        self._update_history(station_id, reading)

        return results

    def _validate_ranges(self, reading: WeatherState) -> List[ValidationResult]:
        results = []

        if not (self.temp_min <= reading.temperature <= self.temp_max):
            results.append(ValidationResult(
                flag=ValidationFlag.FAIL,
                parameter="temperature",
                message=f"Temperature {reading.temperature:.1f}°C outside physical range [{self.temp_min}, {self.temp_max}]",
                value=reading.temperature,
                expected_range=(self.temp_min, self.temp_max),
                severity=90.0
            ))
        elif reading.temperature > 40 or reading.temperature < 0:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING,
                parameter="temperature",
                message=f"Temperature {reading.temperature:.1f}°C is extreme but physically possible",
                value=reading.temperature,
                expected_range=(self.temp_min, self.temp_max),
                severity=40.0
            ))
        else:
            results.append(ValidationResult(
                flag=ValidationFlag.PASS,
                parameter="temperature",
                message="Temperature within normal range",
                value=reading.temperature,
                expected_range=(self.temp_min, self.temp_max),
                severity=0.0
            ))

        if not (self.humidity_min <= reading.humidity <= self.humidity_max):
            results.append(ValidationResult(
                flag=ValidationFlag.FAIL,
                parameter="humidity",
                message=f"Humidity {reading.humidity:.1f}% outside valid range [0, 100]",
                value=reading.humidity,
                expected_range=(self.humidity_min, self.humidity_max),
                severity=90.0
            ))
        else:
            results.append(ValidationResult(
                flag=ValidationFlag.PASS,
                parameter="humidity",
                message="Humidity within valid range",
                value=reading.humidity,
                expected_range=(self.humidity_min, self.humidity_max),
                severity=0.0
            ))

        if not (self.pressure_min <= reading.pressure <= self.pressure_max):
            results.append(ValidationResult(
                flag=ValidationFlag.FAIL,
                parameter="pressure",
                message=f"Pressure {reading.pressure:.1f} hPa outside plausible range [{self.pressure_min}, {self.pressure_max}]",
                value=reading.pressure,
                expected_range=(self.pressure_min, self.pressure_max),
                severity=90.0
            ))
        else:
            results.append(ValidationResult(
                flag=ValidationFlag.PASS,
                parameter="pressure",
                message="Pressure within plausible range",
                value=reading.pressure,
                expected_range=(self.pressure_min, self.pressure_max),
                severity=0.0
            ))

        return results

    def _validate_rate_of_change(self, station_id: str, reading: WeatherState,
                                  prev_reading: Optional[WeatherState]) -> List[ValidationResult]:
        results = []

        if prev_reading is None:
            return results

        time_diff = (reading.timestamp - prev_reading.timestamp).total_seconds() / 60.0
        if time_diff <= 0:
            return results

        temp_rate = abs(reading.temperature - prev_reading.temperature) / time_diff
        if temp_rate > self.max_temp_rate:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING if temp_rate < self.max_temp_rate * 2 else ValidationFlag.FAIL,
                parameter="temperature",
                message=f"Temperature rate of change {temp_rate:.2f}°C/min exceeds threshold {self.max_temp_rate}",
                value=temp_rate,
                expected_range=(0, self.max_temp_rate),
                severity=min(80.0, temp_rate / self.max_temp_rate * 40)
            ))

        humidity_rate = abs(reading.humidity - prev_reading.humidity) / time_diff
        if humidity_rate > self.max_humidity_rate:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING if humidity_rate < self.max_humidity_rate * 2 else ValidationFlag.FAIL,
                parameter="humidity",
                message=f"Humidity rate of change {humidity_rate:.2f}%/min exceeds threshold {self.max_humidity_rate}",
                value=humidity_rate,
                expected_range=(0, self.max_humidity_rate),
                severity=min(70.0, humidity_rate / self.max_humidity_rate * 35)
            ))

        pressure_rate = abs(reading.pressure - prev_reading.pressure) / time_diff
        if pressure_rate > self.max_pressure_rate:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING if pressure_rate < self.max_pressure_rate * 2 else ValidationFlag.FAIL,
                parameter="pressure",
                message=f"Pressure rate of change {pressure_rate:.2f} hPa/min exceeds threshold {self.max_pressure_rate}",
                value=pressure_rate,
                expected_range=(0, self.max_pressure_rate),
                severity=min(60.0, pressure_rate / self.max_pressure_rate * 30)
            ))

        return results

    def _validate_frozen_sensor(self, station_id: str, reading: WeatherState) -> List[ValidationResult]:
        results = []

        if station_id not in self.station_history or len(self.station_history[station_id]) < self.frozen_threshold:
            return results

        recent = self.station_history[station_id][-self.frozen_threshold:]

        temp_frozen = all(abs(r.temperature - recent[0].temperature) < self.frozen_tolerance for r in recent)
        if temp_frozen:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING,
                parameter="temperature",
                message=f"Temperature frozen at {recent[0].temperature:.2f}°C for {self.frozen_threshold} readings",
                value=recent[0].temperature,
                expected_range=(self.temp_min, self.temp_max),
                severity=60.0
            ))

        pressure_frozen = all(abs(r.pressure - recent[0].pressure) < self.frozen_tolerance * 10 for r in recent)
        if pressure_frozen:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING,
                parameter="pressure",
                message=f"Pressure frozen at {recent[0].pressure:.2f} hPa for {self.frozen_threshold} readings",
                value=recent[0].pressure,
                expected_range=(self.pressure_min, self.pressure_max),
                severity=50.0
            ))

        humidity_frozen = all(abs(r.humidity - recent[0].humidity) < self.frozen_tolerance * 10 for r in recent)
        if humidity_frozen:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING,
                parameter="humidity",
                message=f"Humidity frozen at {recent[0].humidity:.2f}% for {self.frozen_threshold} readings",
                value=recent[0].humidity,
                expected_range=(self.humidity_min, self.humidity_max),
                severity=50.0
            ))

        return results

    def _validate_multivariate_consistency(self, reading: WeatherState) -> List[ValidationResult]:
        results = []

        temp = reading.temperature
        humidity = reading.humidity
        pressure = reading.pressure

        if temp > 35 and humidity > 80:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING,
                parameter="multivariate",
                message=f"High temperature ({temp:.1f}°C) with high humidity ({humidity:.1f}%) - verify consistency",
                value=temp,
                expected_range=(self.temp_min, self.temp_max),
                severity=40.0
            ))

        if temp < 5 and humidity < 30:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING,
                parameter="multivariate",
                message=f"Low temperature ({temp:.1f}°C) with low humidity ({humidity:.1f}%) - verify consistency",
                value=temp,
                expected_range=(self.temp_min, self.temp_max),
                severity=35.0
            ))

        if pressure < 980 and temp > 30:
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING,
                parameter="multivariate",
                message=f"Low pressure ({pressure:.1f} hPa) with high temperature ({temp:.1f}°C) - possible storm or sensor issue",
                value=pressure,
                expected_range=(self.pressure_min, self.pressure_max),
                severity=45.0
            ))

        dew_point = temp - (100 - humidity) / 5.0
        if dew_point > temp:
            results.append(ValidationResult(
                flag=ValidationFlag.FAIL,
                parameter="multivariate",
                message=f"Calculated dew point ({dew_point:.1f}°C) exceeds temperature ({temp:.1f}°C) - impossible",
                value=dew_point,
                expected_range=(-20, 50),
                severity=85.0
            ))

        return results

    def _validate_timestamp(self, reading: WeatherState) -> List[ValidationResult]:
        results = []

        now = datetime.utcnow()
        if reading.timestamp > now + timedelta(minutes=5):
            results.append(ValidationResult(
                flag=ValidationFlag.FAIL,
                parameter="timestamp",
                message=f"Future timestamp detected: {reading.timestamp}",
                value=reading.timestamp.timestamp(),
                expected_range=(0, now.timestamp()),
                severity=80.0
            ))

        if reading.timestamp < now - timedelta(days=365):
            results.append(ValidationResult(
                flag=ValidationFlag.WARNING,
                parameter="timestamp",
                message=f"Timestamp very old: {reading.timestamp}",
                value=reading.timestamp.timestamp(),
                expected_range=(0, now.timestamp()),
                severity=30.0
            ))

        return results

    def _update_history(self, station_id: str, reading: WeatherState):
        if station_id not in self.station_history:
            self.station_history[station_id] = []
        self.station_history[station_id].append(reading)
        if len(self.station_history[station_id]) > self.max_history:
            self.station_history[station_id].pop(0)

    def get_rule_based_score(self, validation_results: List[ValidationResult]) -> float:
        if not validation_results:
            return 0.0

        max_severity = max(r.severity for r in validation_results)
        fail_count = sum(1 for r in validation_results if r.flag == ValidationFlag.FAIL)
        warning_count = sum(1 for r in validation_results if r.flag == ValidationFlag.WARNING)

        score = max_severity + fail_count * 10 + warning_count * 5
        return min(100.0, score)

    def get_validation_summary(self, validation_results: List[ValidationResult]) -> Dict[str, Any]:
        return {
            "total_checks": len(validation_results),
            "passed": sum(1 for r in validation_results if r.flag == ValidationFlag.PASS),
            "warnings": sum(1 for r in validation_results if r.flag == ValidationFlag.WARNING),
            "failures": sum(1 for r in validation_results if r.flag == ValidationFlag.FAIL),
            "max_severity": max((r.severity for r in validation_results), default=0.0),
            "rule_score": self.get_rule_based_score(validation_results),
            "details": [
                {
                    "parameter": r.parameter,
                    "flag": r.flag.value,
                    "message": r.message,
                    "severity": r.severity
                }
                for r in validation_results
            ]
        }