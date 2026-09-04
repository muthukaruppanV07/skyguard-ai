import numpy as np
import torch
import shap
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from backend.config import settings
from backend.anomaly.fusion import AnomalyScore
from backend.anomaly.root_cause import RootCauseResult
from backend.preprocessing.feature_engineer import EngineeredFeatures
from backend.simulation.aws_simulator import WeatherState


@dataclass
class ExplanationResult:
    summary: str
    contributing_factors: List[Dict[str, Any]]
    feature_importance: Dict[str, float]
    shap_values: Optional[np.ndarray] = None
    expected_value: Optional[float] = None
    observed_value: Optional[float] = None
    corrected_value: Optional[float] = None
    correction_confidence: float = 0.0
    recommended_action: str = ""


class ExplainabilityEngine:
    def __init__(self):
        self.isolation_forest_explainer = None
        self.autoencoder_explainer = None
        self.feature_names = EngineeredFeatures.feature_names()

    def explain_anomaly(
        self,
        anomaly_score: AnomalyScore,
        root_cause: RootCauseResult,
        reading: WeatherState,
        prev_reading: Optional[WeatherState],
        features: Optional[EngineeredFeatures] = None,
        neighbor_readings: Optional[Dict[str, WeatherState]] = None
    ) -> ExplanationResult:
        factors = []
        feature_importance = {}

        factors.extend(self._explain_rule_based(anomaly_score))
        factors.extend(self._explain_temporal(anomaly_score))
        factors.extend(self._explain_multivariate(anomaly_score))
        factors.extend(self._explain_spatial(anomaly_score, neighbor_readings))
        factors.extend(self._explain_ml_models(anomaly_score, features))

        if features is not None:
            feature_importance = self._compute_feature_importance(features, anomaly_score)

        summary = self._generate_summary(root_cause, factors, anomaly_score)
        expected_value, corrected_value, correction_confidence = self._estimate_corrected_value(
            reading, prev_reading, root_cause, neighbor_readings
        )
        recommended_action = self._generate_recommended_action(root_cause, anomaly_score)

        return ExplanationResult(
            summary=summary,
            contributing_factors=factors,
            feature_importance=feature_importance,
            expected_value=expected_value,
            observed_value=reading.temperature,
            corrected_value=corrected_value,
            correction_confidence=correction_confidence,
            recommended_action=recommended_action
        )

    def _explain_rule_based(self, anomaly_score: AnomalyScore) -> List[Dict[str, Any]]:
        factors = []
        validation = anomaly_score.details.get("validation", {})
        details = validation.get("details", [])

        for detail in details:
            if detail["flag"] in ["FAIL", "WARNING"]:
                factors.append({
                    "source": "Rule-Based QC",
                    "parameter": detail["parameter"],
                    "message": detail["message"],
                    "severity": detail["severity"],
                    "type": "rule_violation"
                })

        return factors

    def _explain_temporal(self, anomaly_score: AnomalyScore) -> List[Dict[str, Any]]:
        factors = []
        temporal = anomaly_score.details.get("temporal", {})

        for key, value in temporal.items():
            if isinstance(value, (int, float)) and value > 30:
                factors.append({
                    "source": "Temporal Analysis",
                    "parameter": key,
                    "message": f"Temporal anomaly detected: {key} score = {value:.1f}",
                    "severity": value,
                    "type": "temporal_anomaly"
                })

        return factors

    def _explain_multivariate(self, anomaly_score: AnomalyScore) -> List[Dict[str, Any]]:
        factors = []
        mv = anomaly_score.details.get("multivariate", {})
        details = mv.get("details", {})

        for name, detail in details.items():
            if detail.get("issue") != "consistent":
                factors.append({
                    "source": "Multivariate Consistency",
                    "parameter": name,
                    "message": f"Physical inconsistency: {detail.get('issue', name)}",
                    "severity": mv.get("component_scores", {}).get(name, 50),
                    "type": "physical_inconsistency"
                })

        return factors

    def _explain_spatial(
        self, anomaly_score: AnomalyScore,
        neighbor_readings: Optional[Dict[str, WeatherState]]
    ) -> List[Dict[str, Any]]:
        factors = []
        spatial = anomaly_score.details.get("spatial", {})

        if spatial.get("neighbor_count", 0) > 0:
            if spatial.get("avg_temp_diff", 0) > 5:
                factors.append({
                    "source": "Spatial Consistency",
                    "parameter": "temperature",
                    "message": f"Temperature differs from {spatial['neighbor_count']} neighbors by {spatial['avg_temp_diff']:.1f}°C",
                    "severity": spatial.get("temp_score", 0),
                    "type": "spatial_deviation"
                })
            if spatial.get("avg_humidity_diff", 0) > 15:
                factors.append({
                    "source": "Spatial Consistency",
                    "parameter": "humidity",
                    "message": f"Humidity differs from neighbors by {spatial['avg_humidity_diff']:.1f}%",
                    "severity": spatial.get("humidity_score", 0),
                    "type": "spatial_deviation"
                })
            if spatial.get("avg_pressure_diff", 0) > 5:
                factors.append({
                    "source": "Spatial Consistency",
                    "parameter": "pressure",
                    "message": f"Pressure differs from neighbors by {spatial['avg_pressure_diff']:.1f} hPa",
                    "severity": spatial.get("pressure_score", 0),
                    "type": "spatial_deviation"
                })

        return factors

    def _explain_ml_models(
        self, anomaly_score: AnomalyScore,
        features: Optional[EngineeredFeatures]
    ) -> List[Dict[str, Any]]:
        factors = []

        if anomaly_score.isolation_forest_score > 30:
            factors.append({
                "source": "Isolation Forest",
                "parameter": "multivariate",
                "message": f"Isolation Forest anomaly score: {anomaly_score.isolation_forest_score:.1f}/100",
                "severity": anomaly_score.isolation_forest_score,
                "type": "ml_anomaly"
            })

        if anomaly_score.autoencoder_score > 30:
            factors.append({
                "source": "Autoencoder",
                "parameter": "multivariate",
                "message": f"Autoencoder reconstruction error score: {anomaly_score.autoencoder_score:.1f}/100",
                "severity": anomaly_score.autoencoder_score,
                "type": "ml_anomaly"
            })

        return factors

    def _compute_feature_importance(
        self, features: EngineeredFeatures, anomaly_score: AnomalyScore
    ) -> Dict[str, float]:
        importance = {}

        feature_dict = features.to_dict()

        for name, value in feature_dict.items():
            if "zscore" in name.lower() and abs(value) > 2:
                importance[name] = min(100.0, abs(value) * 15)
            elif "dev_from_ma" in name.lower() and abs(value) > 2:
                importance[name] = min(100.0, abs(value) * 10)
            elif "rate_of_change" in name.lower() and abs(value) > 1:
                importance[name] = min(100.0, abs(value) * 20)
            elif "change" in name.lower() and abs(value) > 5:
                importance[name] = min(100.0, abs(value) * 5)

        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10])

    def _generate_summary(
        self, root_cause: RootCauseResult, factors: List[Dict], anomaly_score: AnomalyScore
    ) -> str:
        if anomaly_score.severity.value == "NORMAL":
            return "No significant anomalies detected. All weather parameters are within expected ranges."

        param = "temperature"
        if "pressure" in str(root_cause.root_cause).lower():
            param = "pressure"
        elif "humidity" in str(root_cause.root_cause).lower():
            param = "humidity"

        lines = [
            f"Anomaly detected in {param} with severity: {anomaly_score.severity.value} "
            f"(score: {anomaly_score.final_score:.1f}/100, confidence: {anomaly_score.confidence:.1f}%).",
            f"Root cause: {root_cause.root_cause.value.replace('_', ' ').title()} ({root_cause.confidence:.1f}% confidence)."
        ]

        if root_cause.contributing_factors:
            lines.append("Key contributing factors:")
            for factor in root_cause.contributing_factors[:3]:
                lines.append(f"  - {factor}")

        if root_cause.is_real_event_likely:
            lines.append("Note: Neighboring stations show similar patterns, suggesting this may be a genuine weather event.")

        return " ".join(lines)

    def _estimate_corrected_value(
        self,
        reading: WeatherState,
        prev_reading: Optional[WeatherState],
        root_cause: RootCauseResult,
        neighbor_readings: Optional[Dict[str, WeatherState]]
    ) -> Tuple[Optional[float], Optional[float], float]:
        param_map = {
            "temperature": reading.temperature,
            "pressure": reading.pressure,
            "humidity": reading.humidity
        }

        param = "temperature"
        if "pressure" in str(root_cause.root_cause).lower():
            param = "pressure"
        elif "humidity" in str(root_cause.root_cause).lower():
            param = "humidity"

        observed = param_map[param]

        if root_cause.root_cause.value in ["POSSIBLE_REAL_WEATHER_EVENT", "NORMAL"]:
            return observed, observed, 95.0

        expected = None
        confidence = 50.0

        if prev_reading and root_cause.root_cause.value not in ["FROZEN_SENSOR"]:
            expected = getattr(prev_reading, param)
            confidence = 70.0

        if neighbor_readings:
            neighbor_values = [getattr(r, param) for r in neighbor_readings.values()]
            if neighbor_values:
                neighbor_mean = np.mean(neighbor_values)
                if expected is not None:
                    expected = 0.6 * expected + 0.4 * neighbor_mean
                else:
                    expected = neighbor_mean
                confidence = min(90.0, confidence + 15)

        if expected is None:
            expected = observed
            confidence = 10.0

        return expected, expected, confidence

    def _generate_recommended_action(self, root_cause: RootCauseResult, anomaly_score: AnomalyScore) -> str:
        cause = root_cause.root_cause

        actions = {
            "TEMPERATURE_SPIKE": "Inspect temperature sensor for damage or recalibrate. Verify shielding and ventilation.",
            "PRESSURE_SPIKE": "Check barometer for blockages or calibration drift. Verify sensor exposure.",
            "HUMIDITY_SPIKE": "Inspect humidity sensor for contamination. Clean or replace sensor element.",
            "SENSOR_DRIFT": "Schedule sensor recalibration. Check for environmental contamination.",
            "FROZEN_SENSOR": "Sensor appears stuck. Power cycle or replace sensor. Check wiring connections.",
            "MISSING_DATA": "Investigate communication link. Check power supply and network connectivity.",
            "DUPLICATE_DATA": "Check data logger timestamp handling. Verify communication protocol.",
            "COMMUNICATION_FAILURE": "Check network connectivity, power supply, and modem/router status.",
            "MULTIVARIATE_INCONSISTENCY": "Cross-verify all sensors. Likely multiple sensor issues or data corruption.",
            "SENSOR_DEGRADATION": "Sensor showing signs of aging. Plan replacement within maintenance window.",
            "RANDOM_NOISE": "Check for electromagnetic interference. Verify grounding and shielding.",
            "POSSIBLE_SENSOR_MALFUNCTION": "Multiple indicators suggest sensor fault. Schedule field inspection.",
            "POSSIBLE_REAL_WEATHER_EVENT": "Verify with neighboring stations and weather models. No immediate sensor action needed.",
        }

        return actions.get(cause.value, "Monitor and investigate further.")

    def setup_shap_explainers(self, isolation_forest, autoencoder, background_data: np.ndarray):
        if isolation_forest and isolation_forest.is_trained:
            self.isolation_forest_explainer = shap.TreeExplainer(isolation_forest.model)

        if autoencoder and autoencoder.is_trained:
            def model_fn(x):
                x_tensor = torch.from_numpy(x).float().to(autoencoder.device)
                autoencoder.model.eval()
                with torch.no_grad():
                    recon = autoencoder.model(x_tensor)
                    error = torch.mean((x_tensor - recon) ** 2, dim=1)
                return error.cpu().numpy()

            self.autoencoder_explainer = shap.KernelExplainer(model_fn, background_data[:100])

    def get_shap_explanation(self, features: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self.isolation_forest_explainer:
            shap_values = self.isolation_forest_explainer.shap_values(features)
            expected_value = self.isolation_forest_explainer.expected_value
            return shap_values, expected_value
        return None, None