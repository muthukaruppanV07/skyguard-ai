import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.config import settings
from backend.models.sensor_health import SensorType, HealthStatus


class SensorHealthCalculator:
    def __init__(self):
        self.weights = {
            "anomaly": settings.HEALTH_ANOMALY_WEIGHT,
            "drift": settings.HEALTH_DRIFT_WEIGHT,
            "frozen": settings.HEALTH_FROZEN_WEIGHT,
            "missing": settings.HEALTH_MISSING_WEIGHT,
            "comm": settings.HEALTH_COMM_WEIGHT,
            "recon": settings.HEALTH_RECON_WEIGHT,
        }
        self.thresholds = {
            "healthy": settings.HEALTH_HEALTHY_THRESHOLD,
            "warning": settings.HEALTH_WARNING_THRESHOLD,
            "critical": settings.HEALTH_CRITICAL_THRESHOLD,
        }

    def compute_health(
        self,
        station_id: str,
        sensor_type: SensorType,
        anomalies_24h: int,
        anomalies_7d: int,
        drift_detected: bool,
        frozen_count: int,
        missing_count: int,
        comm_failure_count: int,
        reconstruction_error_avg: float,
    ) -> Dict[str, Any]:
        anomaly_score = min(1.0, anomalies_7d / 50.0) * 100
        drift_score = 100 if drift_detected else 0
        frozen_score = min(1.0, frozen_count / 10.0) * 100
        missing_score = min(1.0, missing_count / 20.0) * 100
        comm_score = min(1.0, comm_failure_count / 10.0) * 100
        recon_score = min(1.0, reconstruction_error_avg * 10) * 100

        weighted_penalty = (
            self.weights["anomaly"] * anomaly_score +
            self.weights["drift"] * drift_score +
            self.weights["frozen"] * frozen_score +
            self.weights["missing"] * missing_score +
            self.weights["comm"] * comm_score +
            self.weights["recon"] * recon_score
        )

        health_score = max(0, 100 - weighted_penalty)

        if health_score >= self.thresholds["healthy"]:
            status = HealthStatus.HEALTHY
        elif health_score >= self.thresholds["warning"]:
            status = HealthStatus.WARNING
        elif health_score >= self.thresholds["critical"]:
            status = HealthStatus.MAINTENANCE_RECOMMENDED
        else:
            status = HealthStatus.CRITICAL

        return {
            "sensor_type": sensor_type.value,
            "health_score": round(health_score, 1),
            "status": status.value,
            "components": {
                "anomaly_penalty": round(self.weights["anomaly"] * anomaly_score, 1),
                "drift_penalty": round(self.weights["drift"] * drift_score, 1),
                "frozen_penalty": round(self.weights["frozen"] * frozen_score, 1),
                "missing_penalty": round(self.weights["missing"] * missing_score, 1),
                "comm_penalty": round(self.weights["comm"] * comm_score, 1),
                "recon_penalty": round(self.weights["recon"] * recon_score, 1),
            },
            "raw_metrics": {
                "anomalies_24h": anomalies_24h,
                "anomalies_7d": anomalies_7d,
                "drift_detected": drift_detected,
                "frozen_count": frozen_count,
                "missing_count": missing_count,
                "comm_failures": comm_failure_count,
                "reconstruction_error_avg": reconstruction_error_avg,
            },
        }

    def compute_station_health(
        self,
        station_id: str,
        sensor_health_data: Dict[SensorType, Dict],
    ) -> Dict[str, Any]:
        overall = np.mean([h["health_score"] for h in sensor_health_data.values()])
        
        if overall >= self.thresholds["healthy"]:
            overall_status = HealthStatus.HEALTHY
        elif overall >= self.thresholds["warning"]:
            overall_status = HealthStatus.WARNING
        elif overall >= self.thresholds["critical"]:
            overall_status = HealthStatus.MAINTENANCE_RECOMMENDED
        else:
            overall_status = HealthStatus.CRITICAL

        return {
            "station_id": station_id,
            "overall_score": round(overall, 1),
            "overall_status": overall_status.value,
            "sensors": {k.value: v for k, v in sensor_health_data.items()},
        }


def create_sensor_health_calculator() -> SensorHealthCalculator:
    return SensorHealthCalculator()