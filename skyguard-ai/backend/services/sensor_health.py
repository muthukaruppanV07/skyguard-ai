import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import deque

from backend.config import settings
from backend.database.models import SensorHealth
from backend.anomaly.fusion import AnomalyScore, SeverityLevel
from backend.simulation.aws_simulator import WeatherState


@dataclass
class SensorHealthResult:
    overall_health: float
    temperature_health: float
    pressure_health: float
    humidity_health: float
    status: str
    risk_level: str
    anomaly_count_24h: int
    drift_score: float
    missing_data_ratio: float
    frozen_count: int
    comm_failure_count: int
    avg_reconstruction_error: float
    maintenance_recommendation: Optional[str]
    days_until_maintenance: Optional[int]


class SensorHealthMonitor:
    def __init__(self, window_hours: int = 24):
        self.window_hours = window_hours
        self.station_anomalies: Dict[str, deque] = {}
        self.station_readings: Dict[str, deque] = {}
        self.max_anomaly_history = 1000
        self.max_reading_history = 5000

    def _get_anomaly_buffer(self, station_id: str) -> deque:
        if station_id not in self.station_anomalies:
            self.station_anomalies[station_id] = deque(maxlen=self.max_anomaly_history)
        return self.station_anomalies[station_id]

    def _get_reading_buffer(self, station_id: str) -> deque:
        if station_id not in self.station_readings:
            self.station_readings[station_id] = deque(maxlen=self.max_reading_history)
        return self.station_readings[station_id]

    def record_anomaly(self, station_id: str, anomaly_score: AnomalyScore):
        buffer = self._get_anomaly_buffer(station_id)
        buffer.append({
            "timestamp": anomaly_score.timestamp,
            "score": anomaly_score.final_score,
            "severity": anomaly_score.severity.value,
            "parameter": anomaly_score.parameter,
            "root_cause": anomaly_score.details.get("root_cause", "UNKNOWN")
        })

    def record_reading(self, station_id: str, reading: WeatherState, is_missing: bool = False):
        buffer = self._get_reading_buffer(station_id)
        buffer.append({
            "timestamp": reading.timestamp,
            "temperature": reading.temperature,
            "pressure": reading.pressure,
            "humidity": reading.humidity,
            "is_missing": is_missing
        })

    def compute_health(self, station_id: str) -> SensorHealthResult:
        anomaly_buffer = self._get_anomaly_buffer(station_id)
        reading_buffer = self._get_reading_buffer(station_id)

        now = datetime.utcnow()
        cutoff = now - timedelta(hours=self.window_hours)

        recent_anomalies = [a for a in anomaly_buffer if a["timestamp"] >= cutoff]
        recent_readings = [r for r in reading_buffer if r["timestamp"] >= cutoff]

        anomaly_count = len(recent_anomalies)
        critical_anomalies = [a for a in recent_anomalies if a["severity"] in ["HIGH", "CRITICAL"]]

        temp_health = self._compute_parameter_health(recent_anomalies, recent_readings, "temperature")
        pressure_health = self._compute_parameter_health(recent_anomalies, recent_readings, "pressure")
        humidity_health = self._compute_parameter_health(recent_anomalies, recent_readings, "humidity")

        drift_score = self._compute_drift_score(recent_readings)
        missing_data_ratio = self._compute_missing_ratio(recent_readings)
        frozen_count = self._compute_frozen_count(recent_readings)
        comm_failure_count = self._count_comm_failures(recent_anomalies)
        avg_recon_error = self._compute_avg_recon_error(recent_anomalies)

        overall_health = np.mean([temp_health, pressure_health, humidity_health])
        overall_health = max(0.0, min(100.0, overall_health - anomaly_count * 2 - len(critical_anomalies) * 5))

        status = self._determine_status(overall_health)
        risk_level = self._determine_risk_level(overall_health, drift_score, missing_data_ratio)

        maintenance_rec, days_until = self._generate_maintenance_recommendation(
            overall_health, temp_health, pressure_health, humidity_health,
            drift_score, missing_data_ratio, frozen_count
        )

        return SensorHealthResult(
            overall_health=round(overall_health, 1),
            temperature_health=round(temp_health, 1),
            pressure_health=round(pressure_health, 1),
            humidity_health=round(humidity_health, 1),
            status=status,
            risk_level=risk_level,
            anomaly_count_24h=anomaly_count,
            drift_score=round(drift_score, 3),
            missing_data_ratio=round(missing_data_ratio, 3),
            frozen_count=frozen_count,
            comm_failure_count=comm_failure_count,
            avg_reconstruction_error=round(avg_recon_error, 6),
            maintenance_recommendation=maintenance_rec,
            days_until_maintenance=days_until
        )

    def _compute_parameter_health(
        self, anomalies: List[Dict], readings: List[Dict], parameter: str
    ) -> float:
        param_anomalies = [a for a in anomalies if parameter in a.get("parameter", "").lower()
                          or a.get("parameter") == "multivariate"]

        if not readings:
            return 100.0

        base_health = 100.0
        base_health -= len(param_anomalies) * 5
        base_health -= len([a for a in param_anomalies if a["severity"] in ["HIGH", "CRITICAL"]]) * 10

        param_readings = [r[parameter] for r in readings if not r.get("is_missing", False)]
        if len(param_readings) > 10:
            recent_std = np.std(param_readings[-10:])
            older_std = np.std(param_readings[:-10]) if len(param_readings) > 10 else recent_std
            if older_std > 0 and recent_std / older_std > 2:
                base_health -= 15

        return max(0.0, min(100.0, base_health))

    def _compute_drift_score(self, readings: List[Dict]) -> float:
        if len(readings) < 20:
            return 0.0

        recent = readings[-20:]
        temps = [r["temperature"] for r in recent]
        pressures = [r["pressure"] for r in recent]
        humidities = [r["humidity"] for r in recent]

        x = np.arange(len(temps))
        temp_slope = abs(np.polyfit(x, temps, 1)[0])
        pressure_slope = abs(np.polyfit(x, pressures, 1)[0])
        humidity_slope = abs(np.polyfit(x, humidities, 1)[0]) / 10

        return max(temp_slope, pressure_slope, humidity_slope)

    def _compute_missing_ratio(self, readings: List[Dict]) -> float:
        if not readings:
            return 0.0
        missing = sum(1 for r in readings if r.get("is_missing", False))
        return missing / len(readings)

    def _compute_frozen_count(self, readings: List[Dict]) -> int:
        if len(readings) < 10:
            return 0

        frozen = 0
        for param in ["temperature", "pressure", "humidity"]:
            values = [r[param] for r in readings[-10:]]
            if np.std(values) < 0.01:
                frozen += 1
        return frozen

    def _count_comm_failures(self, anomalies: List[Dict]) -> int:
        return sum(1 for a in anomalies if "COMMUNICATION" in a.get("root_cause", "").upper()
                   or "MISSING" in a.get("root_cause", "").upper())

    def _compute_avg_recon_error(self, anomalies: List[Dict]) -> float:
        if not anomalies:
            return 0.0
        return np.mean([a["score"] for a in anomalies]) / 100.0

    def _determine_status(self, health: float) -> str:
        if health >= settings.HEALTH_WARNING_THRESHOLD:
            return "HEALTHY"
        elif health >= settings.HEALTH_CRITICAL_THRESHOLD:
            return "WARNING"
        else:
            return "MAINTENANCE_RECOMMENDED"

    def _determine_risk_level(self, health: float, drift: float, missing_ratio: float) -> str:
        if health < 40 or drift > 1.0 or missing_ratio > 0.3:
            return "HIGH"
        elif health < 70 or drift > 0.5 or missing_ratio > 0.1:
            return "MEDIUM"
        return "LOW"

    def _generate_maintenance_recommendation(
        self, overall: float, temp: float, pressure: float, humidity: float,
        drift: float, missing: float, frozen: int
    ) -> tuple:
        recommendations = []
        min_health = min(temp, pressure, humidity)

        if min_health < 50:
            if temp < 50:
                recommendations.append("Temperature sensor needs immediate inspection")
            if pressure < 50:
                recommendations.append("Pressure sensor needs immediate inspection")
            if humidity < 50:
                recommendations.append("Humidity sensor needs immediate inspection")
            days = 1
        elif min_health < 70:
            if temp < 70:
                recommendations.append("Temperature sensor calibration recommended")
            if pressure < 70:
                recommendations.append("Pressure sensor calibration recommended")
            if humidity < 70:
                recommendations.append("Humidity sensor calibration recommended")
            days = 7
        elif drift > 0.5:
            recommendations.append("Sensor drift detected. Schedule recalibration.")
            days = 14
        elif missing > 0.1:
            recommendations.append("Communication issues detected. Check connectivity.")
            days = 3
        elif frozen > 0:
            recommendations.append("Frozen sensor readings detected. Check sensor hardware.")
            days = 1
        else:
            return None, None

        return "; ".join(recommendations), days

    def get_all_station_health(self, station_ids: List[str]) -> Dict[str, SensorHealthResult]:
        return {sid: self.compute_health(sid) for sid in station_ids}