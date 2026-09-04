from typing import Dict, Any, List
from backend.config import settings
from backend.models.sensor_health import SensorType


class MaintenanceRiskAssessor:
    def __init__(self):
        self.risk_thresholds = {
            "low": 30,
            "medium": 50,
            "high": 70,
            "critical": 85,
        }

    def assess_risk(
        self,
        station_id: str,
        sensor_health: Dict[SensorType, Dict],
        anomaly_trends: Dict[SensorType, Dict] = None,
    ) -> Dict[str, Any]:
        risks = {}
        recommendations = []

        for sensor_type, health in sensor_health.items():
            score = health["health_score"]
            metrics = health.get("raw_metrics", {})

            risk_factors = []
            risk_score = 0

            if metrics.get("anomalies_7d", 0) > 10:
                risk_factors.append(f"High anomaly frequency ({metrics['anomalies_7d']} in 7 days)")
                risk_score += 30

            if metrics.get("drift_detected"):
                risk_factors.append("Calibration drift detected")
                risk_score += 25

            if metrics.get("frozen_count", 0) > 5:
                risk_factors.append(f"Frozen readings ({metrics['frozen_count']} occurrences)")
                risk_score += 20

            if metrics.get("missing_count", 0) > 10:
                risk_factors.append(f"Frequent missing data ({metrics['missing_count']} gaps)")
                risk_score += 15

            if metrics.get("comm_failures", 0) > 5:
                risk_factors.append(f"Communication issues ({metrics['comm_failures']} failures)")
                risk_score += 15

            if metrics.get("reconstruction_error_avg", 0) > 0.5:
                risk_factors.append(f"High reconstruction error ({metrics['reconstruction_error_avg']:.3f})")
                risk_score += 20

            if anomaly_trends and sensor_type in anomaly_trends:
                trend = anomaly_trends[sensor_type]
                if trend.get("increasing", False):
                    risk_factors.append("Anomaly frequency increasing")
                    risk_score += 15

            risk_score = min(100, risk_score)

            if risk_score >= self.risk_thresholds["critical"]:
                risk_level = "CRITICAL"
            elif risk_score >= self.risk_thresholds["high"]:
                risk_level = "HIGH"
            elif risk_score >= self.risk_thresholds["medium"]:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            if risk_level in ["HIGH", "CRITICAL"]:
                recommendations.append({
                    "sensor": sensor_type.value,
                    "priority": risk_level,
                    "action": f"Inspect {sensor_type.value.lower()} sensor",
                    "reason": "; ".join(risk_factors),
                })

            risks[sensor_type.value] = {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "factors": risk_factors,
            }

        overall_risk = max([r["risk_score"] for r in risks.values()]) if risks else 0
        overall_level = max(risks.values(), key=lambda x: x["risk_score"])["risk_level"] if risks else "LOW"

        return {
            "station_id": station_id,
            "overall_risk_score": overall_risk,
            "overall_risk_level": overall_level,
            "per_sensor": risks,
            "recommendations": recommendations,
            "summary": self._generate_summary(station_id, overall_level, recommendations),
        }

    def _generate_summary(
        self,
        station_id: str,
        risk_level: str,
        recommendations: List[Dict],
    ) -> str:
        if risk_level == "LOW":
            return f"Station {station_id}: All sensors operating normally. No maintenance required."
        elif risk_level == "MEDIUM":
            return f"Station {station_id}: Some sensors showing early degradation signs. Monitor closely."
        else:
            sensors = [r["sensor"] for r in recommendations]
            return (
                f"Station {station_id}: {risk_level} maintenance risk. "
                f"Recommended action: Inspect {', '.join(sensors)} sensor(s)."
            )


def create_maintenance_risk_assessor() -> MaintenanceRiskAssessor:
    return MaintenanceRiskAssessor()