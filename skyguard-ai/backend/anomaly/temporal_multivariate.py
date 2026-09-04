import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque

from backend.config import settings
from backend.simulation.aws_simulator import WeatherState


@dataclass
class TemporalAnomalyResult:
    score: float
    is_anomalous: bool
    details: Dict[str, Any]


class TemporalAnomalyDetector:
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.station_buffers: Dict[str, deque] = {}
        self.seasonal_models: Dict[str, Dict] = {}

    def _get_buffer(self, station_id: str) -> deque:
        if station_id not in self.station_buffers:
            self.station_buffers[station_id] = deque(maxlen=self.window_size)
        return self.station_buffers[station_id]

    def detect(self, station_id: str, reading: WeatherState) -> TemporalAnomalyResult:
        buffer = self._get_buffer(station_id)
        buffer.append(reading)

        if len(buffer) < 10:
            return TemporalAnomalyResult(
                score=0.0,
                is_anomalous=False,
                details={"reason": "insufficient_history"}
            )

        readings = list(buffer)
        scores = {}
        details = {}

        scores["sudden_change"] = self._detect_sudden_change(readings)
        details["sudden_change"] = scores["sudden_change"]

        scores["trend_deviation"] = self._detect_trend_deviation(readings)
        details["trend_deviation"] = scores["trend_deviation"]

        scores["seasonal_deviation"] = self._detect_seasonal_deviation(station_id, reading)
        details["seasonal_deviation"] = scores["seasonal_deviation"]

        scores["pattern_break"] = self._detect_pattern_break(readings)
        details["pattern_break"] = scores["pattern_break"]

        combined_score = np.mean(list(scores.values()))
        is_anomalous = combined_score > 50

        return TemporalAnomalyResult(
            score=combined_score,
            is_anomalous=is_anomalous,
            details=details
        )

    def _detect_sudden_change(self, readings: List[WeatherState]) -> float:
        if len(readings) < 3:
            return 0.0

        current = readings[-1]
        prev = readings[-2]
        prev2 = readings[-3]

        temp_diff1 = abs(current.temperature - prev.temperature)
        temp_diff2 = abs(prev.temperature - prev2.temperature)

        if temp_diff2 > 0:
            ratio = temp_diff1 / temp_diff2
            if ratio > 5:
                return min(100.0, ratio * 10)

        pressure_diff1 = abs(current.pressure - prev.pressure)
        pressure_diff2 = abs(prev.pressure - prev2.pressure)

        if pressure_diff2 > 0:
            ratio = pressure_diff1 / pressure_diff2
            if ratio > 5:
                return min(100.0, ratio * 10)

        humidity_diff1 = abs(current.humidity - prev.humidity)
        humidity_diff2 = abs(prev.humidity - prev2.humidity)

        if humidity_diff2 > 0:
            ratio = humidity_diff1 / humidity_diff2
            if ratio > 5:
                return min(100.0, ratio * 10)

        return 0.0

    def _detect_trend_deviation(self, readings: List[WeatherState]) -> float:
        if len(readings) < 10:
            return 0.0

        recent = readings[-10:]
        temps = np.array([r.temperature for r in recent])
        pressures = np.array([r.pressure for r in recent])
        humidities = np.array([r.humidity for r in recent])

        x = np.arange(len(temps))
        temp_slope = np.polyfit(x, temps, 1)[0]
        pressure_slope = np.polyfit(x, pressures, 1)[0]
        humidity_slope = np.polyfit(x, humidities, 1)[0]

        current = readings[-1]
        prev = readings[-2]

        expected_temp = prev.temperature + temp_slope
        expected_pressure = prev.pressure + pressure_slope
        expected_humidity = prev.humidity + humidity_slope

        temp_dev = abs(current.temperature - expected_temp)
        pressure_dev = abs(current.pressure - expected_pressure)
        humidity_dev = abs(current.humidity - expected_humidity)

        temp_std = np.std(temps[:-1]) if len(temps) > 1 else 1.0
        pressure_std = np.std(pressures[:-1]) if len(pressures) > 1 else 1.0
        humidity_std = np.std(humidities[:-1]) if len(humidities) > 1 else 1.0

        temp_score = min(100.0, (temp_dev / max(temp_std, 0.1)) * 20)
        pressure_score = min(100.0, (pressure_dev / max(pressure_std, 0.1)) * 20)
        humidity_score = min(100.0, (humidity_dev / max(humidity_std, 0.1)) * 20)

        return max(temp_score, pressure_score, humidity_score)

    def _detect_seasonal_deviation(self, station_id: str, reading: WeatherState) -> float:
        hour = reading.timestamp.hour
        day_of_year = reading.timestamp.timetuple().tm_yday

        key = f"{station_id}_{hour}_{day_of_year // 7}"

        if key not in self.seasonal_models:
            self.seasonal_models[key] = {
                "temps": [],
                "pressures": [],
                "humidities": [],
                "count": 0
            }

        model = self.seasonal_models[key]
        model["temps"].append(reading.temperature)
        model["pressures"].append(reading.pressure)
        model["humidities"].append(reading.humidity)
        model["count"] += 1

        if model["count"] < 5:
            return 0.0

        temp_mean = np.mean(model["temps"])
        temp_std = np.std(model["temps"]) if len(model["temps"]) > 1 else 1.0
        pressure_mean = np.mean(model["pressures"])
        pressure_std = np.std(model["pressures"]) if len(model["pressures"]) > 1 else 1.0
        humidity_mean = np.mean(model["humidities"])
        humidity_std = np.std(model["humidities"]) if len(model["humidities"]) > 1 else 1.0

        temp_z = abs(reading.temperature - temp_mean) / max(temp_std, 0.5)
        pressure_z = abs(reading.pressure - pressure_mean) / max(pressure_std, 0.5)
        humidity_z = abs(reading.humidity - humidity_mean) / max(humidity_std, 0.5)

        max_z = max(temp_z, pressure_z, humidity_z)
        return min(100.0, max_z * 15)

    def _detect_pattern_break(self, readings: List[WeatherState]) -> float:
        if len(readings) < 20:
            return 0.0

        first_half = readings[-20:-10]
        second_half = readings[-10:]

        first_temps = np.array([r.temperature for r in first_half])
        second_temps = np.array([r.temperature for r in second_half])

        first_mean = np.mean(first_temps)
        first_std = np.std(first_temps) if len(first_temps) > 1 else 1.0

        last_temp = readings[-1].temperature
        z_score = abs(last_temp - first_mean) / max(first_std, 0.5)

        return min(100.0, z_score * 12)


class MultivariateConsistencyChecker:
    def __init__(self):
        self.physical_relationships = {
            "temp_humidity": self._check_temp_humidity,
            "temp_pressure": self._check_temp_pressure,
            "pressure_humidity": self._check_pressure_humidity,
            "dew_point": self._check_dew_point,
        }

    def check_consistency(self, reading: WeatherState) -> Dict[str, Any]:
        results = {}
        scores = {}

        for name, check_func in self.physical_relationships.items():
            score, detail = check_func(reading)
            scores[name] = score
            results[name] = detail

        overall_score = np.mean(list(scores.values()))
        is_consistent = overall_score < 50

        return {
            "overall_score": overall_score,
            "is_consistent": is_consistent,
            "component_scores": scores,
            "details": results
        }

    def _check_temp_humidity(self, reading: WeatherState) -> Tuple[float, Dict]:
        temp = reading.temperature
        humidity = reading.humidity

        if temp > 35 and humidity > 80:
            return 70.0, {"issue": "high_temp_high_humidity", "temp": temp, "humidity": humidity}
        if temp < 5 and humidity < 30:
            return 50.0, {"issue": "low_temp_low_humidity", "temp": temp, "humidity": humidity}

        expected_humidity = 100 - (temp * 1.5)
        deviation = abs(humidity - expected_humidity)
        if deviation > 40:
            return min(80.0, deviation), {"issue": "humidity_deviation", "expected": expected_humidity, "actual": humidity}

        return 0.0, {"status": "consistent"}

    def _check_temp_pressure(self, reading: WeatherState) -> Tuple[float, Dict]:
        temp = reading.temperature
        pressure = reading.pressure

        if pressure < 990 and temp > 30:
            return 60.0, {"issue": "low_pressure_high_temp", "pressure": pressure, "temp": temp}

        expected_pressure = 1013.25 - (temp - 20) * 0.3
        deviation = abs(pressure - expected_pressure)
        if deviation > 15:
            return min(70.0, deviation * 2), {"issue": "pressure_deviation", "expected": expected_pressure, "actual": pressure}

        return 0.0, {"status": "consistent"}

    def _check_pressure_humidity(self, reading: WeatherState) -> Tuple[float, Dict]:
        pressure = reading.pressure
        humidity = reading.humidity

        if pressure < 1000 and humidity < 40:
            return 55.0, {"issue": "low_pressure_low_humidity", "pressure": pressure, "humidity": humidity}

        return 0.0, {"status": "consistent"}

    def _check_dew_point(self, reading: WeatherState) -> Tuple[float, Dict]:
        temp = reading.temperature
        humidity = reading.humidity

        if humidity <= 0:
            return 0.0, {"status": "humidity_zero"}

        a = 17.27
        b = 237.7
        alpha = ((a * temp) / (b + temp)) + np.log(humidity / 100.0)
        dew_point = (b * alpha) / (a - alpha)

        if dew_point > temp:
            return 90.0, {"issue": "dew_point_exceeds_temp", "dew_point": dew_point, "temp": temp}

        if dew_point > temp - 0.5:
            return 30.0, {"issue": "dew_point_near_temp", "dew_point": dew_point, "temp": temp}

        return 0.0, {"status": "consistent", "dew_point": dew_point}