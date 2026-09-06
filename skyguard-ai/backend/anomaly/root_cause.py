import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from backend.config import settings
from backend.anomaly.fusion import AnomalyScore, SeverityLevel
from backend.simulation.aws_simulator import WeatherState
from backend.simulation.anomaly_injector import FaultType


class RootCause(str, Enum):
    NORMAL = "NORMAL"
    TEMPERATURE_SPIKE = "TEMPERATURE_SPIKE"
    PRESSURE_SPIKE = "PRESSURE_SPIKE"
    HUMIDITY_SPIKE = "HUMIDITY_SPIKE"
    SENSOR_DRIFT = "SENSOR_DRIFT"
    FROZEN_SENSOR = "FROZEN_SENSOR"
    MISSING_DATA = "MISSING_DATA"
    DUPLICATE_DATA = "DUPLICATE_DATA"
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"
    MULTIVARIATE_INCONSISTENCY = "MULTIVARIATE_INCONSISTENCY"
    POSSIBLE_SENSOR_MALFUNCTION = "POSSIBLE_SENSOR_MALFUNCTION"
    POSSIBLE_REAL_WEATHER_EVENT = "POSSIBLE_REAL_WEATHER_EVENT"
    SENSOR_DEGRADATION = "SENSOR_DEGRADATION"
    RANDOM_NOISE = "RANDOM_NOISE"


@dataclass
class RootCauseResult:
    root_cause: RootCause
    confidence: float
    reasoning: str
    contributing_factors: List[str]
    is_real_event_likely: bool


class RootCauseClassifier:
    def __init__(self):
        self.station_history: Dict[str, List[WeatherState]] = {}
        self.max_history = 200

    def classify(
        self,
        station_id: str,
        reading: WeatherState,
        prev_reading: Optional[WeatherState],
        anomaly_score: AnomalyScore,
        neighbor_readings: Optional[Dict[str, WeatherState]] = None
    ) -> RootCauseResult:
        if anomaly_score.severity == SeverityLevel.NORMAL:
            return RootCauseResult(
                root_cause=RootCause.NORMAL,
                confidence=95.0,
                reasoning="All parameters within normal ranges, no anomalies detected",
                contributing_factors=[],
                is_real_event_likely=False
            )

        self._update_history(station_id, reading)

        factors = []
        cause_scores = {}

        cause_scores[RootCause.TEMPERATURE_SPIKE] = self._check_temperature_spike(reading, prev_reading, anomaly_score, factors)
        cause_scores[RootCause.PRESSURE_SPIKE] = self._check_pressure_spike(reading, prev_reading, anomaly_score, factors)
        cause_scores[RootCause.HUMIDITY_SPIKE] = self._check_humidity_spike(reading, prev_reading, anomaly_score, factors)
        cause_scores[RootCause.SENSOR_DRIFT] = self._check_sensor_drift(station_id, reading, anomaly_score, factors)
        cause_scores[RootCause.FROZEN_SENSOR] = self._check_frozen_sensor(station_id, reading, anomaly_score, factors)
        cause_scores[RootCause.MULTIVARIATE_INCONSISTENCY] = self._check_multivariate_inconsistency(reading, anomaly_score, factors)
        cause_scores[RootCause.SENSOR_DEGRADATION] = self._check_sensor_degradation(station_id, reading, anomaly_score, factors)
        cause_scores[RootCause.RANDOM_NOISE] = self._check_random_noise(reading, prev_reading, anomaly_score, factors)

        real_event_score = self._check_real_weather_event(station_id, reading, neighbor_readings, anomaly_score, factors)
        cause_scores[RootCause.POSSIBLE_REAL_WEATHER_EVENT] = real_event_score

        sensor_malfunction_score = self._check_sensor_malfunction(anomaly_score, factors)
        cause_scores[RootCause.POSSIBLE_SENSOR_MALFUNCTION] = sensor_malfunction_score

        sorted_causes = sorted(cause_scores.items(), key=lambda x: x[1], reverse=True)
        top_cause, top_score = sorted_causes[0]

        confidence = min(99.0, max(10.0, top_score + 20))

        if top_cause == RootCause.POSSIBLE_REAL_WEATHER_EVENT and real_event_score > 60:
            is_real_event = True
        else:
            is_real_event = False

        reasoning = self._generate_reasoning(top_cause, reading, prev_reading, neighbor_readings, anomaly_score)

        return RootCauseResult(
            root_cause=top_cause,
            confidence=confidence,
            reasoning=reasoning,
            contributing_factors=factors,
            is_real_event_likely=is_real_event
        )

    def _check_temperature_spike(
        self, reading: WeatherState, prev_reading: Optional[WeatherState],
        anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        if prev_reading is None:
            return 0.0

        temp_change = abs(reading.temperature - prev_reading.temperature)
        time_diff = (reading.timestamp - prev_reading.timestamp).total_seconds() / 60.0

        if time_diff > 0:
            rate = temp_change / time_diff
            if rate > 5.0:
                factors.append(f"Temperature spike: {temp_change:.1f}°C in {time_diff:.0f} min (rate: {rate:.1f}°C/min)")
                return min(95.0, rate * 8)
            elif rate > 2.0:
                factors.append(f"Rapid temperature change: {rate:.1f}°C/min")
                return min(70.0, rate * 15)

        return 0.0

    def _check_pressure_spike(
        self, reading: WeatherState, prev_reading: Optional[WeatherState],
        anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        if prev_reading is None:
            return 0.0

        pressure_change = abs(reading.pressure - prev_reading.pressure)
        time_diff = (reading.timestamp - prev_reading.timestamp).total_seconds() / 60.0

        if time_diff > 0:
            rate = pressure_change / time_diff
            if rate > 3.0:
                factors.append(f"Pressure spike: {pressure_change:.1f} hPa in {time_diff:.0f} min")
                return min(90.0, rate * 15)
            elif rate > 1.0:
                factors.append(f"Rapid pressure change: {rate:.1f} hPa/min")
                return min(60.0, rate * 25)

        return 0.0

    def _check_humidity_spike(
        self, reading: WeatherState, prev_reading: Optional[WeatherState],
        anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        if prev_reading is None:
            return 0.0

        humidity_change = abs(reading.humidity - prev_reading.humidity)
        time_diff = (reading.timestamp - prev_reading.timestamp).total_seconds() / 60.0

        if time_diff > 0:
            rate = humidity_change / time_diff
            if rate > 10.0:
                factors.append(f"Humidity spike: {humidity_change:.1f}% in {time_diff:.0f} min")
                return min(85.0, rate * 4)
            elif rate > 5.0:
                factors.append(f"Rapid humidity change: {rate:.1f}%/min")
                return min(55.0, rate * 6)

        return 0.0

    def _check_sensor_drift(
        self, station_id: str, reading: WeatherState,
        anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        if station_id not in self.station_history or len(self.station_history[station_id]) < 20:
            return 0.0

        history = self.station_history[station_id][-20:]
        temps = [r.temperature for r in history]
        pressures = [r.pressure for r in history]
        humidities = [r.humidity for r in history]

        x = np.arange(len(temps))
        temp_slope = np.polyfit(x, temps, 1)[0]
        pressure_slope = np.polyfit(x, pressures, 1)[0]
        humidity_slope = np.polyfit(x, humidities, 1)[0]

        max_slope = max(abs(temp_slope), abs(pressure_slope), abs(humidity_slope) / 10)

        if max_slope > 0.5:
            factors.append(f"Sensor drift detected: max slope {max_slope:.3f} per reading")
            return min(85.0, max_slope * 50)

        return 0.0

    def _check_frozen_sensor(
        self, station_id: str, reading: WeatherState,
        anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        if station_id not in self.station_history or len(self.station_history[station_id]) < 10:
            return 0.0

        history = self.station_history[station_id][-10:]
        temps = [r.temperature for r in history]
        pressures = [r.pressure for r in history]
        humidities = [r.humidity for r in history]

        temp_frozen = np.std(temps) < 0.02
        pressure_frozen = np.std(pressures) < 0.02
        humidity_frozen = np.std(humidities) < 0.02

        if temp_frozen or pressure_frozen or humidity_frozen:
            frozen_params = []
            if temp_frozen:
                frozen_params.append(f"temperature ({temps[0]:.2f}°C)")
            if pressure_frozen:
                frozen_params.append(f"pressure ({pressures[0]:.2f} hPa)")
            if humidity_frozen:
                frozen_params.append(f"humidity ({humidities[0]:.2f}%)")
            factors.append(f"Frozen sensor(s): {', '.join(frozen_params)} for 10 readings")
            return 90.0

        return 0.0

    def _check_multivariate_inconsistency(
        self, reading: WeatherState, anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        mv_details = anomaly_score.details.get("multivariate", {})
        mv_score = mv_details.get("overall_score", 0)

        if mv_score > 50:
            for name, detail in mv_details.get("details", {}).items():
                if detail.get("issue") != "consistent":
                    factors.append(f"Multivariate inconsistency: {detail.get('issue', name)}")
            return min(85.0, mv_score)

        return 0.0

    def _check_sensor_degradation(
        self, station_id: str, reading: WeatherState,
        anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        if station_id not in self.station_history or len(self.station_history[station_id]) < 50:
            return 0.0

        history = self.station_history[station_id][-50:]
        recent = history[-10:]
        older = history[-50:-10]

        recent_temp_std = np.std([r.temperature for r in recent])
        older_temp_std = np.std([r.temperature for r in older])

        recent_humidity_std = np.std([r.humidity for r in recent])
        older_humidity_std = np.std([r.humidity for r in older])

        if older_temp_std > 0 and recent_temp_std / older_temp_std > 3:
            factors.append(f"Temperature noise increased {recent_temp_std/older_temp_std:.1f}x (degradation)")
            return 75.0

        if older_humidity_std > 0 and recent_humidity_std / older_humidity_std > 3:
            factors.append(f"Humidity noise increased {recent_humidity_std/older_humidity_std:.1f}x (degradation)")
            return 75.0

        return 0.0

    def _check_random_noise(
        self, reading: WeatherState, prev_reading: Optional[WeatherState],
        anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        if prev_reading is None:
            return 0.0

        temp_change = abs(reading.temperature - prev_reading.temperature)
        pressure_change = abs(reading.pressure - prev_reading.pressure)
        humidity_change = abs(reading.humidity - prev_reading.humidity)

        if temp_change > 3 and pressure_change < 1 and humidity_change < 5:
            factors.append("Isolated temperature noise spike")
            return 40.0

        return 0.0

    def _check_real_weather_event(
        self, station_id: str, reading: WeatherState,
        neighbor_readings: Optional[Dict[str, WeatherState]],
        anomaly_score: AnomalyScore, factors: List[str]
    ) -> float:
        if not neighbor_readings:
            return 30.0

        neighbor_temps = [r.temperature for r in neighbor_readings.values()]
        neighbor_humidities = [r.humidity for r in neighbor_readings.values()]
        neighbor_pressures = [r.pressure for r in neighbor_readings.values()]

        temp_diff = abs(reading.temperature - np.mean(neighbor_temps))
        humidity_diff = abs(reading.humidity - np.mean(neighbor_humidities))
        pressure_diff = abs(reading.pressure - np.mean(neighbor_pressures))

        if temp_diff < 3 and humidity_diff < 10 and pressure_diff < 3:
            factors.append("Neighboring stations show similar readings - likely real weather event")
            return 80.0
        elif temp_diff < 5 and humidity_diff < 15 and pressure_diff < 5:
            factors.append("Neighboring stations show moderately similar readings")
            return 50.0
        else:
            factors.append(f"Neighboring stations differ significantly (ΔT={temp_diff:.1f}°C, ΔH={humidity_diff:.1f}%, ΔP={pressure_diff:.1f} hPa)")
            return 10.0

    def _check_sensor_malfunction(self, anomaly_score: AnomalyScore, factors: List[str]) -> float:
        high_components = 0
        if anomaly_score.rule_score > 50:
            high_components += 1
        if anomaly_score.isolation_forest_score > 50:
            high_components += 1
        if anomaly_score.autoencoder_score > 50:
            high_components += 1
        if anomaly_score.temporal_score > 50:
            high_components += 1
        if anomaly_score.multivariate_score > 50:
            high_components += 1
        if anomaly_score.spatial_score > 50:
            high_components += 1

        if high_components >= 3:
            factors.append(f"Multiple detection systems agree ({high_components}/6 components flagged)")
            return min(90.0, 40 + high_components * 10)

        return 0.0

    def _generate_reasoning(
        self, cause: RootCause, reading: WeatherState,
        prev_reading: Optional[WeatherState],
        neighbor_readings: Optional[Dict[str, WeatherState]],
        anomaly_score: AnomalyScore
    ) -> str:
        param = "temperature"
        if cause in [RootCause.PRESSURE_SPIKE, RootCause.POSSIBLE_SENSOR_MALFUNCTION]:
            param = "pressure"
        elif cause in [RootCause.HUMIDITY_SPIKE]:
            param = "humidity"

        if cause == RootCause.NORMAL:
            return "All parameters within normal operational ranges."

        if cause == RootCause.POSSIBLE_REAL_WEATHER_EVENT:
            return (f"Observed {param} anomaly ({getattr(reading, param):.1f}) is consistent with "
                    f"nearby station readings, suggesting a genuine meteorological event rather than sensor failure.")

        if cause in [RootCause.TEMPERATURE_SPIKE, RootCause.PRESSURE_SPIKE, RootCause.HUMIDITY_SPIKE]:
            return (f"Sudden {param} change detected that exceeds physically plausible rates of change. "
                    f"This pattern is characteristic of a sensor malfunction rather than natural variation.")

        if cause == RootCause.SENSOR_DRIFT:
            return (f"Gradual drift in {param} readings over time indicates sensor calibration issue "
                    f"or environmental contamination of the sensor.")

        if cause == RootCause.FROZEN_SENSOR:
            return (f"{param.capitalize()} sensor reporting identical values across multiple readings, "
                    f"indicating a stuck/frozen sensor.")

        if cause == RootCause.MULTIVARIATE_INCONSISTENCY:
            return (f"Atmospheric parameters show physically inconsistent relationships "
                    f"(e.g., temperature-humidity-pressure combination violates thermodynamic constraints).")

        if cause == RootCause.SENSOR_DEGRADATION:
            return (f"Increasing measurement noise over time suggests progressive sensor degradation "
                    f"requiring maintenance.")

        if cause == RootCause.POSSIBLE_SENSOR_MALFUNCTION:
            return (f"Multiple independent detection methods flag this observation as anomalous. "
                    f"While the exact failure mode is uncertain, sensor malfunction is highly probable.")

        return f"Anomaly classified as {cause.value} based on pattern analysis."

    def _update_history(self, station_id: str, reading: WeatherState):
        if station_id not in self.station_history:
            self.station_history[station_id] = []
        self.station_history[station_id].append(reading)
        if len(self.station_history[station_id]) > self.max_history:
            self.station_history[station_id].pop(0)