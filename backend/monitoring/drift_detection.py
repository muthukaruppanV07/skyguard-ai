import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from scipy import stats
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
from pathlib import Path
import json
from collections import defaultdict


class DriftType(Enum):
    DATA_DRIFT = "data_drift"
    CONCEPT_DRIFT = "concept_drift"
    PREDICTION_DRIFT = "prediction_drift"
    FEATURE_DRIFT = "feature_drift"


class DriftSeverity(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftAlert:
    drift_type: DriftType
    severity: DriftSeverity
    feature: str
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: datetime
    station_id: str = ""
    model_name: str = ""
    acknowledged: bool = False


@dataclass
class ModelMetrics:
    timestamp: datetime
    model_name: str
    station_id: str
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    auc: float = 0.0
    prediction_rate: float = 0.0
    anomaly_rate: float = 0.0
    avg_score: float = 0.0
    latency_ms: float = 0.0


class FeatureDistributionMonitor:
    def __init__(self, feature_names: List[str], window_size: int = 1000):
        self.feature_names = feature_names
        self.window_size = window_size
        self.reference_stats = {}
        self.current_windows = {f: deque(maxlen=window_size) for f in feature_names}
        self.drift_history = []
    
    def set_reference(self, data: np.ndarray):
        df = pd.DataFrame(data, columns=self.feature_names)
        for feature in self.feature_names:
            values = df[feature].dropna().values
            self.reference_stats[feature] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'q25': np.percentile(values, 25),
                'q75': np.percentile(values, 75),
                'hist': np.histogram(values, bins=50, density=True)[0],
                'bins': np.histogram(values, bins=50, density=True)[1]
            }
    
    def add_batch(self, data: np.ndarray):
        df = pd.DataFrame(data, columns=self.feature_names)
        for feature in self.feature_names:
            self.current_windows[feature].extend(df[feature].dropna().values)
    
    def check_drift(self, threshold_ks: float = 0.05, threshold_psi: float = 0.2) -> List[DriftAlert]:
        alerts = []
        for feature in self.feature_names:
            if feature not in self.reference_stats:
                continue
            
            current_values = np.array(self.current_windows[feature])
            if len(current_values) < 50:
                continue
            
            ref_stats = self.reference_stats[feature]
            
            ks_stat, p_value = stats.ks_2samp(
                current_values,
                np.random.normal(ref_stats['mean'], ref_stats['std'], len(current_values))
            )
            
            current_hist, _ = np.histogram(current_values, bins=ref_stats['bins'], density=True)
            ref_hist = ref_stats['hist']
            
            psi = np.sum((current_hist - ref_hist) * np.log((current_hist + 1e-10) / (ref_hist + 1e-10)))
            
            mean_shift = abs(np.mean(current_values) - ref_stats['mean']) / (ref_stats['std'] + 1e-6)
            std_shift = abs(np.std(current_values) - ref_stats['std']) / (ref_stats['std'] + 1e-6)
            
            if p_value < threshold_ks or psi > threshold_psi or mean_shift > 2 or std_shift > 1.5:
                severity = self._calculate_severity(p_value, psi, mean_shift, std_shift)
                
                alert = DriftAlert(
                    drift_type=DriftType.FEATURE_DRIFT,
                    severity=severity,
                    feature=feature,
                    metric="ks_test" if p_value < threshold_ks else "psi" if psi > threshold_psi else "mean_shift",
                    value=p_value if p_value < threshold_ks else psi if psi > threshold_psi else mean_shift,
                    threshold=threshold_ks if p_value < threshold_ks else threshold_psi if psi > threshold_psi else 2.0,
                    message=f"Feature drift detected in {feature}: KS p-value={p_value:.4f}, PSI={psi:.4f}, mean_shift={mean_shift:.2f}σ",
                    timestamp=datetime.utcnow()
                )
                alerts.append(alert)
                self.drift_history.append(alert)
        
        return alerts
    
    def _calculate_severity(self, p_value: float, psi: float, mean_shift: float, std_shift: float) -> 'DriftSeverity':
        if p_value < 0.001 or psi > 0.5 or mean_shift > 5:
            return DriftSeverity.CRITICAL
        elif p_value < 0.01 or psi > 0.3 or mean_shift > 3:
            return DriftSeverity.HIGH
        elif p_value < 0.05 or psi > 0.2 or mean_shift > 2:
            return DriftSeverity.MEDIUM
        else:
            return DriftSeverity.LOW


class PredictionDriftMonitor:
    def __init__(self, window_size: int = 5000):
        self.window_size = window_size
        self.prediction_history = deque(maxlen=window_size)
        self.reference_distribution = None
        
    def set_reference(self, predictions: np.ndarray):
        self.reference_distribution = {
            'mean': np.mean(predictions),
            'std': np.std(predictions),
            'hist': np.histogram(predictions, bins=50, density=True)[0],
            'bins': np.histogram(predictions, bins=50, density=True)[1]
        }
    
    def add_predictions(self, predictions: np.ndarray, scores: np.ndarray, labels: np.ndarray = None):
        for pred, score, label in zip(predictions, scores, labels if labels is not None else [None]*len(predictions)):
            self.prediction_history.append({
                'prediction': pred,
                'score': score,
                'label': label,
                'timestamp': datetime.utcnow()
            })
    
    def check_drift(self, threshold: float = 0.1) -> List[DriftAlert]:
        if self.reference_distribution is None or len(self.prediction_history) < 100:
            return []
        
        alerts = []
        recent_preds = np.array([p['prediction'] for p in self.prediction_history])
        recent_scores = np.array([p['score'] for p in self.prediction_history])
        
        psi = self._calculate_psi(
            self.reference_distribution['hist'],
            np.histogram(recent_scores, bins=self.reference_distribution['bins'], density=True)[0]
        )
        
        mean_shift = abs(np.mean(recent_scores) - self.reference_distribution['mean']) / (self.reference_distribution['std'] + 1e-6)
        
        if psi > 0.2 or mean_shift > 2:
            severity = DriftSeverity.HIGH if psi > 0.5 or mean_shift > 3 else DriftSeverity.MEDIUM
            alert = DriftAlert(
                drift_type=DriftType.PREDICTION_DRIFT,
                severity=severity,
                feature="anomaly_score",
                metric="psi" if psi > 0.2 else "mean_shift",
                value=psi if psi > 0.2 else mean_shift,
                threshold=0.2 if psi > 0.2 else 2.0,
                message=f"Prediction drift detected: PSI={psi:.4f}, mean_shift={mean_shift:.2f}σ",
                timestamp=datetime.utcnow()
            )
            alerts.append(alert)
        
        return alerts
    
    def _calculate_psi(self, expected: np.ndarray, actual: np.ndarray) -> float:
        expected = np.clip(expected, 1e-10, 1.0)
        actual = np.clip(actual, 1e-10, 1.0)
        return np.sum((actual - expected) * np.log(actual / expected))


class ConceptDriftMonitor:
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.performance_history = deque(maxlen=window_size)
        self.reference_performance = None
    
    def set_reference_performance(self, metrics: Dict[str, float]):
        self.reference_performance = metrics
    
    def add_performance(self, metrics: ModelMetrics):
        self.performance_history.append(metrics)
    
    def check_drift(self, threshold: float = 0.05) -> List[DriftAlert]:
        if self.reference_performance is None or len(self.performance_history) < 50:
            return []
        
        alerts = []
        recent = list(self.performance_history)[-50:]
        
        for metric in ['accuracy', 'precision', 'recall', 'f1']:
            ref_value = self.reference_performance.get(metric, 0)
            recent_values = [getattr(m, metric) for m in recent]
            current_mean = np.mean(recent_values)
            
            if ref_value > 0:
                relative_drop = (ref_value - current_mean) / ref_value
                if relative_drop > threshold:
                    severity = DriftSeverity.HIGH if relative_drop > 0.15 else DriftSeverity.MEDIUM
                    alert = DriftAlert(
                        drift_type=DriftType.CONCEPT_DRIFT,
                        severity=severity,
                        feature=metric,
                        metric="performance_drop",
                        value=relative_drop,
                        threshold=threshold,
                        message=f"Concept drift detected: {metric} dropped by {relative_drop:.1%}",
                        timestamp=datetime.utcnow()
                    )
                    alerts.append(alert)
        
        return alerts


class ModelMonitor:
    def __init__(
        self,
        model_name: str,
        feature_names: List[str],
        drift_check_interval: int = 100,
        window_size: int = 5000
    ):
        self.model_name = model_name
        self.feature_names = feature_names
        self.drift_check_interval = drift_check_interval
        self.window_size = window_size
        
        self.feature_monitor = FeatureDistributionMonitor(feature_names, window_size)
        self.prediction_monitor = PredictionDriftMonitor(window_size)
        self.concept_monitor = ConceptDriftMonitor(window_size)
        
        self.prediction_count = 0
        self.alerts = deque(maxlen=1000)
        self.metrics_history = deque(maxlen=10000)
        self.is_initialized = False
        self.last_check = 0
        
    def initialize(self, reference_data: np.ndarray, reference_predictions: np.ndarray, reference_metrics: Dict = None):
        self.feature_monitor.set_reference(reference_data)
        self.prediction_monitor.set_reference(reference_predictions)
        
        if reference_metrics:
            self.concept_monitor.set_reference_performance(reference_metrics)
        
        self.is_initialized = True
    
    def record_prediction(
        self,
        features: np.ndarray,
        prediction: int,
        score: float,
        label: int = None,
        station_id: str = "",
        latency_ms: float = 0.0
    ):
        self.prediction_count += 1
        
        self.feature_monitor.add_batch(features.reshape(1, -1))
        self.prediction_monitor.add_predictions(
            np.array([prediction]), 
            np.array([score]), 
            np.array([label]) if label is not None else None
        )
        
        if self.prediction_count % self.drift_check_interval == 0:
            self._check_all_drifts(station_id)
    
    def record_metrics(self, metrics: ModelMetrics):
        self.metrics_history.append(metrics)
        self.concept_monitor.add_performance(metrics)
        
        if len(self.metrics_history) % self.drift_check_interval == 0:
            self._check_concept_drift()
    
    def _check_all_drifts(self, station_id: str):
        feature_alerts = self.feature_monitor.check_drift()
        for alert in feature_alerts:
            alert.station_id = station_id
            alert.model_name = self.model_name
            self.alerts.append(alert)
        
        pred_alerts = self.prediction_monitor.check_drift()
        for alert in pred_alerts:
            alert.station_id = station_id
            alert.model_name = self.model_name
            self.alerts.append(alert)
    
    def _check_concept_drift(self):
        alerts = self.concept_monitor.check_drift()
        for alert in alerts:
            alert.model_name = self.model_name
            self.alerts.append(alert)
    
    def get_alerts(self, unacknowledged_only: bool = True, limit: int = 100) -> List[DriftAlert]:
        alerts = list(self.alerts)
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return alerts[-limit:]
    
    def acknowledge_alert(self, alert_index: int) -> bool:
        if 0 <= alert_index < len(self.alerts):
            alerts_list = list(self.alerts)
            if 0 <= alert_index < len(alerts_list):
                alerts_list[alert_index].acknowledged = True
                self.alerts = deque(alerts_list, maxlen=1000)
                return True
        return False
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "is_initialized": self.is_initialized,
            "total_predictions": self.prediction_count,
            "total_alerts": len(self.alerts),
            "unacknowledged_alerts": len([a for a in self.alerts if not a.acknowledged]),
            "critical_alerts": len([a for a in self.alerts if a.severity == DriftSeverity.CRITICAL]),
            "feature_drift_count": len(self.feature_monitor.drift_history),
            "prediction_drift_count": len(self.prediction_monitor.prediction_history),
            "last_check": self.last_check,
            "feature_stats": {
                f: {
                    "current_mean": np.mean(self.feature_monitor.current_windows[f]) if self.feature_monitor.current_windows[f] else 0,
                    "reference_mean": self.feature_monitor.reference_stats.get(f, {}).get('mean', 0)
                }
                for f in self.feature_names
            }
        }


class MultiModelMonitor:
    def __init__(self):
        self.monitors: Dict[str, ModelMonitor] = {}
        self.global_alerts = deque(maxlen=5000)
    
    def add_model(self, monitor: ModelMonitor):
        self.monitors[monitor.model_name] = monitor
    
    def record_prediction(self, model_name: str, *args, **kwargs):
        if model_name in self.monitors:
            self.monitors[model_name].record_prediction(*args, **kwargs)
    
    def record_metrics(self, model_name: str, metrics: ModelMetrics):
        if model_name in self.monitors:
            self.monitors[model_name].record_metrics(metrics)
    
    def get_all_alerts(self, unacknowledged_only: bool = True, limit: int = 100) -> List[DriftAlert]:
        all_alerts = []
        for monitor in self.monitors.values():
            all_alerts.extend(monitor.get_alerts(unacknowledged_only, limit))
        
        all_alerts.sort(key=lambda x: x.timestamp, reverse=True)
        return all_alerts[:limit]
    
    def get_system_health(self) -> Dict[str, Any]:
        total_models = len(self.monitors)
        total_alerts = sum(len(m.alerts) for m in self.monitors.values())
        critical_alerts = sum(
            len([a for a in m.alerts if a.severity == 'critical']) 
            for m in self.monitors.values()
        )
        unacknowledged = sum(
            len([a for a in m.alerts if not a.acknowledged]) 
            for m in self.monitors.values()
        )
        
        return {
            "total_models": total_models,
            "total_alerts": total_alerts,
            "critical_alerts": critical_alerts,
            "unacknowledged_alerts": unacknowledged,
            "models": {
                name: m.get_monitoring_summary() 
                for name, m in self.monitors.items()
            }
        }
    
    def acknowledge_alert(self, model_name: str, alert_index: int) -> bool:
        if model_name in self.monitors:
            return self.monitors[model_name].acknowledge_alert(alert_index)
        return False


def create_model_monitor(model_name: str, feature_names: List[str]) -> ModelMonitor:
    return ModelMonitor(model_name, feature_names)


def create_multi_model_monitor() -> MultiModelMonitor:
    return MultiModelMonitor()