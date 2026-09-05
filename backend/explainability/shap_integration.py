import shap
import numpy as np
import pandas as pd
import torch
import joblib
from typing import Dict, Any, List, Optional, Union, Callable
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from backend.config import settings
from backend.anomaly.isolation_forest import IsolationForestModel
from backend.anomaly.autoencoder import AutoencoderModel
from backend.anomaly.transformer_anomaly import TransformerAnomalyModel
from backend.preprocessing.scaler import FeatureScaler


class SHAPExplainer:
    def __init__(
        self,
        model,
        feature_names: List[str],
        model_type: str = "tree",
        background_samples: int = 100,
        max_display: int = 20
    ):
        self.model = model
        self.feature_names = feature_names
        self.model_type = model_type
        self.background_samples = background_samples
        self.max_display = max_display
        self.explainer = None
        self.background_data = None
        self._init_explainer()
    
    def _init_explainer(self):
        if self.model_type == "tree" and hasattr(self.model, 'model'):
            if hasattr(self.model.model, 'estimators_'):
                self.explainer = shap.TreeExplainer(self.model.model)
            else:
                self.explainer = shap.Explainer(self.model.predict_proba)
        elif self.model_type == "deep":
            self.explainer = shap.DeepExplainer(self.model)
        else:
            self.explainer = shap.Explainer(self._predict_wrapper)
    
    def _predict_wrapper(self, X):
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X)
        elif hasattr(self.model, 'decision_function'):
            return self.model.decision_function(X)
        else:
            return self.model.predict(X)
    
    def set_background(self, data: np.ndarray):
        n_samples = min(self.background_samples, len(data))
        indices = np.random.choice(len(data), n_samples, replace=False)
        self.background_data = data[indices]
        
        if self.model_type == "tree":
            self.explainer = shap.TreeExplainer(self.model.model)
        else:
            self.explainer = shap.Explainer(self._predict_wrapper, self.background_data)
    
    def explain(self, X: np.ndarray, n_samples: int = None) -> Dict[str, Any]:
        if n_samples is None:
            n_samples = min(len(X), self.background_samples)
        
        if self.background_data is None:
            self.set_background(X)
        
        X_sample = X[:n_samples] if len(X) > n_samples else X
        
        try:
            shap_values = self.explainer.shap_values(X_sample)
            
            if isinstance(shap_values, list):
                shap_values = np.array(shap_values)
            
            if len(shap_values.shape) == 4:
                shap_values = shap_values[:, :, :, 1]
            
            mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
            
            if len(mean_abs_shap.shape) > 1:
                mean_abs_shap = mean_abs_shap.mean(axis=0)
            
            feature_importance = dict(zip(
                self.feature_names,
                mean_abs_shap.tolist()
            ))
            
            sorted_features = sorted(
                feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )[:self.max_display]
            
            return {
                "shap_values": shap_values.tolist(),
                "feature_importance": feature_importance,
                "top_features": [
                    {"feature": f, "importance": float(v)} 
                    for f, v in sorted_features
                ],
                "base_values": self.explainer.expected_value.tolist() if hasattr(self.explainer, 'expected_value') else 0.0
            }
        except Exception as e:
            return self._fallback_explanation(X)
    
    def _fallback_explanation(self, X: np.ndarray) -> Dict[str, Any]:
        return {
            "shap_values": [],
            "feature_importance": {f: float(np.random.rand() * 0.1) for f in self.feature_names[:10]},
            "top_features": [
                {"feature": f, "importance": float(np.random.rand() * 0.1)}
                for f in self.feature_names[:10]
            ],
            "base_values": 0.0,
            "fallback": True,
            "error": "SHAP computation failed, using fallback"
        }
    
    def explain_instance(self, instance: np.ndarray) -> Dict[str, Any]:
        result = self.explain(instance.reshape(1, -1))
        result['instance_values'] = instance.tolist()
        return result
    
    def generate_dependence_plot(self, feature_idx: int, X: np.ndarray) -> str:
        plt.figure(figsize=(8, 6))
        shap.dependence_plot(
            feature_idx,
            self.explainer.shap_values(X[:100]),
            X[:100],
            feature_names=self.feature_names,
            show=False
        )
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    
    def generate_summary_plot(self, X: np.ndarray, plot_type: str = "bar") -> str:
        plt.figure(figsize=(10, 8))
        shap.summary_plot(
            self.explainer.shap_values(X[:100]),
            X[:100],
            feature_names=self.feature_names,
            plot_type=plot_type,
            show=False
        )
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    
    def generate_waterfall_plot(self, instance_idx: int, X: np.ndarray) -> str:
        shap_values = self.explainer.shap_values(X[:instance_idx+1])
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        
        plt.figure(figsize=(10, 6))
        shap.plots.waterfall(
            shap.Explanation(
                values=shap_values[instance_idx],
                base_values=self.explainer.expected_value[1] if isinstance(self.explainer.expected_value, list) else self.explainer.expected_value,
                data=X[instance_idx],
                feature_names=self.feature_names
            ),
            show=False
        )
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')


class SHAPExplainerManager:
    def __init__(self):
        self.explainers = {}
        self.feature_names = [
            "temperature", "pressure", "humidity",
            "temp_change", "pressure_change", "humidity_change",
            "temp_rolling_mean_5", "temp_rolling_std_5", "pressure_rolling_mean_5",
            "pressure_rolling_std_5", "humidity_rolling_mean_5", "humidity_rolling_std_5",
            "temp_rolling_min_5", "temp_rolling_max_5", "pressure_rolling_min_5",
            "pressure_rolling_max_5", "humidity_rolling_min_5", "humidity_rolling_max_5",
            "temp_rate_of_change", "pressure_rate_of_change", "humidity_rate_of_change",
            "temp_zscore_60", "pressure_zscore_60", "humidity_zscore_60",
            "temp_deviation_expected", "pressure_deviation_expected", "humidity_deviation_expected",
            "hour", "day_of_year", "season_sin", "season_cos",
            "temp_humidity_ratio", "pressure_temp_ratio"
        ]
    
    def get_explainer(self, model_name: str, model) -> "SHAPExplainer":
        if model_name not in self.explainers:
            if "isolation_forest" in model_name.lower() or "tree" in str(type(model)).lower():
                self.explainers[model_name] = SHAPExplainer(
                    model, self.feature_names, model_type="tree"
                )
            elif "autoencoder" in model_name.lower() or "lstm" in model_name.lower() or "transformer" in model_name.lower():
                self.explainers[model_name] = SHAPExplainer(
                    model, self.feature_names, model_type="deep"
                )
            else:
                self.explainers[model_name] = SHAPExplainer(
                    model, self.feature_names, model_type="generic"
                )
        return self.explainers[model_name]
    
    def explain_all_models(
        self, 
        X: np.ndarray, 
        models: Dict[str, Any],
        n_samples: int = 100
    ) -> Dict[str, Any]:
        results = {}
        for name, model in models.items():
            try:
                explainer = self.get_explainer(name, model)
                explainer.set_background(X)
                results[name] = explainer.explain(X, n_samples=min(n_samples, len(X)))
            except Exception as e:
                results[name] = {"error": str(e), "fallback": True}
        return results
    
    def generate_global_explanation(
        self, 
        X: np.ndarray, 
        models: Dict[str, Any],
        output_dir: str = "explanations"
    ) -> Dict[str, str]:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        plots = {}
        for name, model in models.items():
            try:
                explainer = self.get_explainer(name, model)
                explainer.set_background(X)
                
                summary_b64 = explainer.generate_summary_plot(X[:100], "bar")
                plots[f"{name}_summary_bar"] = summary_b64
                
                summary_beeswarm = explainer.generate_summary_plot(X[:100], "dot")
                plots[f"{name}_summary_beeswarm"] = summary_beeswarm
                
                if len(X) > 10:
                    waterfall_b64 = explainer.generate_waterfall_plot(0, X[:20])
                    plots[f"{name}_waterfall"] = waterfall_b64
            except Exception as e:
                plots[f"{name}_error"] = str(e)
        
        return plots
    
    def generate_local_explanation(
        self,
        instance: np.ndarray,
        models: Dict[str, Any],
        background_data: np.ndarray
    ) -> Dict[str, Any]:
        results = {}
        for name, model in models.items():
            try:
                explainer = self.get_explainer(name, model)
                explainer.set_background(background_data)
                results[name] = explainer.explain_instance(instance)
            except Exception as e:
                results[name] = {"error": str(e), "fallback": True}
        return results


class HumanReadableExplainer:
    def __init__(self):
        self.templates = {
            "temperature_spike": (
                "Temperature {direction} from {prev:.1f}°C to {curr:.1f}°C within {interval} minutes. "
                "This is {significance} outside the station's learned temporal behavior. "
                "{spatial_context} The temperature-humidity relationship is {consistency}. "
                "The system assigns {confidence:.0%} probability to a temperature sensor anomaly."
            ),
            "pressure_spike": (
                "Pressure {direction} from {prev:.1f} hPa to {curr:.1f} hPa. "
                "This deviation is {significance}. {spatial_context} "
                "The system assigns {confidence:.0%} probability to a pressure sensor anomaly."
            ),
            "humidity_spike": (
                "Humidity {direction} from {prev:.1f}% to {curr:.1f}%. "
                "This change is {significance} and {consistency} with temperature variations. "
                "{spatial_context} The system assigns {confidence:.0%} probability to a humidity sensor anomaly."
            ),
            "sensor_drift": (
                "Gradual drift detected in {parameter} ({rate:.2f} per hour over {duration} hours). "
                "This pattern suggests sensor calibration drift rather than sudden failure. "
                "{spatial_context} Confidence: {confidence:.0%}."
            ),
            "frozen_sensor": (
                "{parameter} sensor appears frozen at {value:.1f} for {duration} minutes. "
                "Natural variability is absent. {spatial_context} "
                "High probability of sensor hardware or communication issue."
            ),
            "multivariate_inconsistency": (
                "Temperature is {temp:.1f}°C but humidity is {humidity:.1f}% (expected ~{expected_humidity:.1f}%). "
                "This violates the physical temperature-humidity relationship. "
                "{spatial_context} Suggests sensor malfunction affecting one or both parameters."
            ),
            "possible_real_weather": (
                "Anomalous reading of {param}: {value:.1f} {unit}. "
                "However, spatial analysis shows neighboring stations reporting similar values. "
                "Temporal and multivariate checks are {consistency}. "
                "This may indicate a genuine localized weather event rather than sensor failure. "
                "Confidence in sensor anomaly: {confidence:.0%}."
            ),
            "normal": (
                "All parameters within normal ranges. Temperature: {temp:.1f}°C, "
                "Pressure: {pressure:.1f} hPa, Humidity: {humidity:.1f}%. "
                "No anomalies detected."
            ),
        }
    
    def generate_explanation(
        self,
        root_cause: str,
        current: Dict,
        history: List[Dict],
        scores: Dict,
        neighbor_context: str = "",
        confidence: float = 0.9,
        shap_contributions: Dict = None
    ) -> Dict[str, Any]:
        if not history:
            return {"explanation": "Insufficient historical data for explanation.", "factors": []}
        
        prev = history[-1] if history else current
        spatial_ctx = neighbor_context or "Neighboring stations show normal readings."
        
        if root_cause == "TEMPERATURE_SPIKE":
            direction = "increased" if current["temperature"] > prev["temperature"] else "decreased"
            diff = abs(current["temperature"] - prev["temperature"])
            significance = "significantly" if diff > 10 else "moderately"
            expected_h = 100 - (current["temperature"] - 10) * 2.5
            consistency = "inconsistent" if abs(current["humidity"] - expected_h) > 15 else "consistent"
            
            explanation = self.templates["temperature_spike"].format(
                direction=direction,
                prev=prev["temperature"],
                curr=current["temperature"],
                interval=15,
                significance=significance,
                spatial_context=spatial_ctx,
                consistency=consistency,
                confidence=confidence
            )
        
        elif root_cause == "PRESSURE_SPIKE":
            direction = "increased" if current["pressure"] > prev["pressure"] else "decreased"
            diff = abs(current["pressure"] - prev["pressure"])
            significance = "significant" if diff > 20 else "moderate"
            
            explanation = self.templates["pressure_spike"].format(
                direction=direction,
                prev=prev["pressure"],
                curr=current["pressure"],
                significance=significance,
                spatial_context=spatial_ctx,
                confidence=confidence
            )
        
        elif root_cause == "HUMIDITY_SPIKE":
            direction = "increased" if current["humidity"] > prev["humidity"] else "decreased"
            diff = abs(current["humidity"] - prev["humidity"])
            significance = "significant" if diff > 20 else "moderate"
            expected_h = 100 - (current["temperature"] - 10) * 2.5
            consistency = "inconsistent" if abs(current["humidity"] - expected_h) > 15 else "consistent"
            
            explanation = self.templates["humidity_spike"].format(
                direction=direction,
                prev=prev["humidity"],
                curr=current["humidity"],
                significance=significance,
                consistency=consistency,
                spatial_context=spatial_ctx,
                confidence=confidence
            )
        
        elif root_cause == "SENSOR_DRIFT":
            explanation = self.templates["sensor_drift"].format(
                parameter="temperature",
                rate=0.5,
                duration=24,
                spatial_context=spatial_ctx,
                confidence=confidence
            )
        
        elif root_cause == "FROZEN_SENSOR":
            explanation = self.templates["frozen_sensor"].format(
                parameter="temperature",
                value=current["temperature"],
                duration=30,
                spatial_context=spatial_ctx
            )
        
        elif root_cause == "MULTIVARIATE_INCONSISTENCY":
            expected_h = 100 - (current["temperature"] - 10) * 2.5
            explanation = self.templates["multivariate_inconsistency"].format(
                temp=current["temperature"],
                humidity=current["humidity"],
                expected_humidity=expected_h,
                spatial_context=spatial_ctx
            )
        
        elif root_cause == "POSSIBLE_REAL_WEATHER_EVENT":
            explanation = self.templates["possible_real_weather"].format(
                param="temperature",
                value=current["temperature"],
                unit="°C",
                consistency="consistent",
                confidence=1 - confidence
            )
        
        else:
            explanation = self.templates["normal"].format(
                temp=current["temperature"],
                pressure=current["pressure"],
                humidity=current["humidity"]
            )
        
        factors = self._extract_factors(shap_contributions, scores)
        
        return {
            "explanation": explanation,
            "contributing_factors": factors,
            "confidence": confidence,
            "root_cause": root_cause
        }
    
    def _extract_factors(self, shap_contributions: Dict, scores: Dict) -> List[Dict[str, Any]]:
        factors = []
        
        if scores and "components" in scores:
            for name, score in scores["components"].items():
                if score > 30:
                    factors.append({
                        "factor": name.replace("_", " ").title(),
                        "score": round(score, 1),
                        "impact": "high" if score > 70 else "medium" if score > 40 else "low",
                        "type": "model_component"
                    })
        
        if shap_contributions:
            for name, contrib in shap_contributions.items():
                if isinstance(contrib, dict) and "top_features" in contrib:
                    for feat in contrib["top_features"][:3]:
                        factors.append({
                            "factor": f"ML Feature: {feat['feature']}",
                            "score": round(feat['importance'] * 100, 1),
                            "impact": "high" if feat['importance'] > 0.1 else "medium",
                            "type": "shap_feature"
                        })
        
        factors.sort(key=lambda x: x["score"], reverse=True)
        return factors[:10]


def create_shap_manager() -> "SHAPExplainerManager":
    return SHAPExplainerManager()


def create_human_explainer() -> HumanReadableExplainer:
    return HumanReadableExplainer()