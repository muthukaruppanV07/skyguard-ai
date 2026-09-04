from typing import Dict, Any
from backend.config import settings, SEVERITY_LEVELS, SEVERITY_COLORS


class AnomalyFusion:
    def __init__(self):
        self.weights = {
            "rule": settings.RULE_WEIGHT,
            "isolation_forest": settings.ISOLATION_FOREST_WEIGHT,
            "autoencoder": settings.AUTOENCODER_WEIGHT,
            "temporal": settings.TEMPORAL_WEIGHT,
            "multivariate": settings.MULTIVARIATE_WEIGHT,
            "spatial": settings.SPATIAL_WEIGHT,
        }

    def fuse(
        self,
        rule_score: float,
        if_score: float,
        ae_score: float,
        temporal_score: float,
        multivariate_score: float,
        spatial_score: float,
    ) -> Dict[str, Any]:
        weighted_sum = (
            self.weights["rule"] * rule_score +
            self.weights["isolation_forest"] * if_score +
            self.weights["autoencoder"] * ae_score +
            self.weights["temporal"] * temporal_score +
            self.weights["multivariate"] * multivariate_score +
            self.weights["spatial"] * spatial_score
        )

        anomaly_score = round(min(100, max(0, weighted_sum)), 2)

        severity = self._get_severity(anomaly_score)
        confidence = self._compute_confidence(
            rule_score, if_score, ae_score, temporal_score, multivariate_score, spatial_score
        )

        return {
            "anomaly_score": anomaly_score,
            "severity": severity,
            "severity_color": SEVERITY_COLORS[severity],
            "confidence": round(confidence, 3),
            "components": {
                "rule": round(rule_score, 2),
                "isolation_forest": round(if_score, 2),
                "autoencoder": round(ae_score, 2),
                "temporal": round(temporal_score, 2),
                "multivariate": round(multivariate_score, 2),
                "spatial": round(spatial_score, 2),
            },
            "weights": self.weights,
        }

    def _get_severity(self, score: float) -> str:
        for level, (low, high) in SEVERITY_LEVELS.items():
            if low <= score < high:
                return level
        return "CRITICAL" if score >= 100 else "NORMAL"

    def _compute_confidence(
        self,
        rule_score: float,
        if_score: float,
        ae_score: float,
        temporal_score: float,
        multivariate_score: float,
        spatial_score: float,
    ) -> float:
        scores = [rule_score, if_score, ae_score, temporal_score, multivariate_score, spatial_score]
        
        mean_score = sum(scores) / len(scores)
        std_score = (sum((s - mean_score) ** 2 for s in scores) / len(scores)) ** 0.5
        
        agreement = 1.0 - min(1.0, std_score / 50.0)
        
        high_components = sum(1 for s in scores if s > 70)
        low_components = sum(1 for s in scores if s < 30)
        
        if high_components >= 4:
            confidence_boost = 0.2
        elif low_components >= 4:
            confidence_boost = 0.1
        else:
            confidence_boost = 0.0

        base_confidence = agreement * 0.8 + 0.2
        final_confidence = min(1.0, base_confidence + confidence_boost)

        return final_confidence


def create_anomaly_fusion() -> AnomalyFusion:
    return AnomalyFusion()