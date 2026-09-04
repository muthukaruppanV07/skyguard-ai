import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from backend.config import settings
from backend.anomaly.temporal_multivariate import TemporalAnomalyDetector, MultivariateConsistencyChecker
from backend.anomaly.spatial import SpatialConsistencyChecker
from backend.anomaly.isolation_forest import IsolationForestDetector
from backend.anomaly.autoencoder import AutoencoderDetector
from backend.preprocessing.data_validator import DataValidator, ValidationResult
from backend.simulation.aws_simulator import WeatherState


class SeverityLevel(str, Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AnomalyScore:
    station_id: str
    timestamp: datetime
    parameter: str
    observed_value: float

    rule_score: float = 0.0
    isolation_forest_score: float = 0.0
    autoencoder_score: float = 0.0
    temporal_score: float = 0.0
    multivariate_score: float = 0.0
    spatial_score: float = 0.0

    final_score: float = 0.0
    severity: SeverityLevel = SeverityLevel.NORMAL
    confidence: float = 0.0

    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class AnomalyFusionEngine:
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        thresholds: Optional[Dict[str, float]] = None
    ):
        self.weights = weights or {
            "rule_based": settings.WEIGHT_RULE_BASED,
            "isolation_forest": settings.WEIGHT_ISOLATION_FOREST,
            "autoencoder": settings.WEIGHT_AUTOENCODER,
            "temporal": settings.WEIGHT_TEMPORAL,
            "multivariate": settings.WEIGHT_MULTIVARIATE,
            "spatial": settings.WEIGHT_SPATIAL
        }

        self.thresholds = thresholds or {
            "normal_max": settings.SCORE_NORMAL_MAX,
            "low_max": settings.SCORE_LOW_MAX,
            "suspicious_max": settings.SCORE_SUSPICIOUS_MAX,
            "high_max": settings.SCORE_HIGH_MAX
        }

        self.rule_validator = DataValidator()
        self.temporal_detector = TemporalAnomalyDetector()
        self.multivariate_checker = MultivariateConsistencyChecker()
        self.spatial_checker = SpatialConsistencyChecker()
        self.isolation_forest: Optional[IsolationForestDetector] = None
        self.autoencoder: Optional[AutoencoderDetector] = None

    def set_ml_models(self, isolation_forest: IsolationForestDetector, autoencoder: AutoencoderDetector):
        self.isolation_forest = isolation_forest
        self.autoencoder = autoencoder

    def compute_anomaly_score(
        self,
        station_id: str,
        reading: WeatherState,
        prev_reading: Optional[WeatherState],
        neighbor_readings: Optional[Dict[str, WeatherState]],
        features: Optional[np.ndarray] = None
    ) -> AnomalyScore:
        score = AnomalyScore(
            station_id=station_id,
            timestamp=reading.timestamp,
            parameter="multivariate",
            observed_value=reading.temperature
        )

        validation_results = self.rule_validator.validate_reading(station_id, reading, prev_reading)
        score.rule_score = self.rule_validator.get_rule_based_score(validation_results)
        score.details["validation"] = self.rule_validator.get_validation_summary(validation_results)

        temporal_result = self.temporal_detector.detect(station_id, reading)
        score.temporal_score = temporal_result.score
        score.details["temporal"] = temporal_result.details

        multivariate_result = self.multivariate_checker.check_consistency(reading)
        score.multivariate_score = multivariate_result["overall_score"]
        score.details["multivariate"] = multivariate_result

        if neighbor_readings:
            spatial_result = self.spatial_checker.check_spatial_consistency(station_id, reading, neighbor_readings)
            score.spatial_score = spatial_result.score
            score.details["spatial"] = spatial_result.details
        else:
            score.spatial_score = 0.0
            score.details["spatial"] = {"reason": "no_neighbors"}

        if self.isolation_forest and self.isolation_forest.is_trained and features is not None:
            _, iso_score = self.isolation_forest.predict_single(features)
            score.isolation_forest_score = iso_score
        else:
            score.isolation_forest_score = 0.0

        if self.autoencoder and self.autoencoder.is_trained and features is not None:
            _, ae_score, _ = self.autoencoder.predict_single(features)
            score.autoencoder_score = ae_score
        else:
            score.autoencoder_score = 0.0

        score.final_score = self._compute_weighted_score(score)
        score.severity = self._determine_severity(score.final_score)
        score.confidence = self._compute_confidence(score)

        return score

    def _compute_weighted_score(self, score: AnomalyScore) -> float:
        weighted_sum = (
            score.rule_score * self.weights["rule_based"] +
            score.isolation_forest_score * self.weights["isolation_forest"] +
            score.autoencoder_score * self.weights["autoencoder"] +
            score.temporal_score * self.weights["temporal"] +
            score.multivariate_score * self.weights["multivariate"] +
            score.spatial_score * self.weights["spatial"]
        )
        return min(100.0, weighted_sum)

    def _determine_severity(self, final_score: float) -> SeverityLevel:
        if final_score <= self.thresholds["normal_max"]:
            return SeverityLevel.NORMAL
        elif final_score <= self.thresholds["low_max"]:
            return SeverityLevel.LOW
        elif final_score <= self.thresholds["suspicious_max"]:
            return SeverityLevel.SUSPICIOUS
        elif final_score <= self.thresholds["high_max"]:
            return SeverityLevel.HIGH
        else:
            return SeverityLevel.CRITICAL

    def _compute_confidence(self, score: AnomalyScore) -> float:
        component_scores = [
            score.rule_score,
            score.isolation_forest_score,
            score.autoencoder_score,
            score.temporal_score,
            score.multivariate_score,
            score.spatial_score
        ]

        non_zero = [s for s in component_scores if s > 0]
        if not non_zero:
            return 50.0

        agreement = 1.0 - (np.std(non_zero) / max(np.mean(non_zero), 1.0))
        agreement = max(0.0, min(1.0, agreement))

        max_component = max(component_scores)
        confidence = 0.4 + 0.3 * (max_component / 100.0) + 0.3 * agreement

        return min(99.0, max(10.0, confidence * 100))