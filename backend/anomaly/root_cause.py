from typing import Dict, Any, List
from backend.config import settings, ROOT_CAUSE_TYPES
from backend.models.anomaly import RootCause


class RootCauseClassifier:
    def __init__(self, confidence_threshold: float = settings.ROOT_CAUSE_CONFIDENCE_THRESHOLD):
        self.confidence_threshold = confidence_threshold

    def classify(
        self,
        current: Dict,
        history: List[Dict],
        scores: Dict[str, float],
        neighbor_data: Dict = None,
        spatial_score: float = 0,
        multivariate_score: float = 0,
    ) -> Dict[str, Any]:
        evidence = []
        
        rule_details = scores.get("rule_details", {})
        temporal_details = scores.get("temporal_details", {})
        mv_details = scores.get("multivariate_details", {})
        
        temp_val = current["temperature"]
        pressure_val = current["pressure"]
        humidity_val = current["humidity"]

        cause_scores = {cause: 0.0 for cause in ROOT_CAUSE_TYPES}

        if rule_details.get("details", {}).get("frozen_detected"):
            cause_scores[RootCause.FROZEN_SENSOR.value] += 0.9
            evidence.append("Sensor readings frozen (constant values)")

        if rule_details.get("details", {}).get("gap_detected"):
            cause_scores[RootCause.COMMUNICATION_FAILURE.value] += 0.8
            evidence.append("Data gaps detected")

        if rule_details.get("details", {}).get("duplicate_detected"):
            cause_scores[RootCause.DUPLICATE_DATA.value] += 0.9
            evidence.append("Duplicate timestamps detected")

        if rule_details.get("details", {}).get("range_violated"):
            cause_scores[RootCause.POSSIBLE_SENSOR_MALFUNCTION.value] += 0.6
            evidence.append("Values outside plausible range")

        if temporal_details.get("components", {}).get("spike", 0) > 50:
            if temp_val > 45:
                cause_scores[RootCause.TEMPERATURE_SPIKE.value] += 0.9
                evidence.append(f"Temperature spike detected: {temp_val:.1f}°C")
            elif pressure_val > 1050:
                cause_scores[RootCause.PRESSURE_SPIKE.value] += 0.9
                evidence.append(f"Pressure spike detected: {pressure_val:.1f} hPa")
            elif humidity_val > 95 or humidity_val < 5:
                cause_scores[RootCause.HUMIDITY_SPIKE.value] += 0.9
                evidence.append(f"Humidity spike detected: {humidity_val:.1f}%")

        if temporal_details.get("components", {}).get("drift", 0) > 40:
            cause_scores[RootCause.SENSOR_DRIFT.value] += 0.8
            evidence.append("Gradual sensor drift detected")

        if mv_details.get("components", {}).get("temp_humidity", 0) > 50:
            cause_scores[RootCause.MULTIVARIATE_INCONSISTENCY.value] += 0.7
            evidence.append("Temperature-humidity relationship violated")

        if mv_details.get("components", {}).get("overall_consistency", 0) > 50:
            cause_scores[RootCause.MULTIVARIATE_INCONSISTENCY.value] += 0.6
            evidence.append("Multivariate consistency check failed")

        if spatial_score > 70:
            if scores.get("components", {}).get("isolation_forest", 0) > 60:
                cause_scores[RootCause.POSSIBLE_SENSOR_MALFUNCTION.value] += 0.8
                evidence.append("Spatial inconsistency: neighbors show normal values")
            else:
                cause_scores[RootCause.POSSIBLE_REAL_WEATHER_EVENT.value] += 0.6
                evidence.append("Spatial pattern suggests possible real weather event")

        if max(cause_scores.values()) < 0.3:
            cause_scores[RootCause.NORMAL.value] = 0.5
            evidence.append("No significant anomaly patterns detected")

        sorted_causes = sorted(cause_scores.items(), key=lambda x: x[1], reverse=True)
        top_cause = sorted_causes[0][0]
        top_score = sorted_causes[0][1]

        confidence = min(1.0, top_score)

        if confidence < self.confidence_threshold:
            top_cause = RootCause.POSSIBLE_SENSOR_MALFUNCTION.value
            evidence.append(f"Low confidence ({confidence:.1%}), defaulting to possible sensor malfunction")

        return {
            "root_cause": top_cause,
            "confidence": round(confidence, 3),
            "evidence": evidence,
            "all_scores": {k: round(v, 3) for k, v in cause_scores.items() if v > 0},
        }


def create_root_cause_classifier() -> RootCauseClassifier:
    return RootCauseClassifier()