import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import numpy as np
import pandas as pd


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    timestamp: datetime
    value: float
    label: str = ""


@dataclass
class ModelPerformance:
    model_name: str
    model_type: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    latency_ms: float
    throughput: float
    memory_mb: float
    last_updated: datetime
    training_time: float
    epochs: int


@dataclass
class DriftAlert:
    model_name: str
    drift_type: str
    severity: str
    metric: str
    value: float
    threshold: float
    timestamp: datetime
    acknowledged: bool = False


@dataclass
class SystemHealth:
    status: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, float]
    active_models: int
    total_predictions: int
    error_rate: float
    avg_latency: float


class PerformanceDashboard:
    def __init__(self):
        self.model_performance: Dict[str, ModelPerformance] = {}
        self.metrics_history: Dict[str, List[MetricPoint]] = defaultdict(list)
        self.drift_alerts: List[DriftAlert] = []
        self.system_health = SystemHealth(
            status="healthy",
            cpu_percent=0,
            memory_percent=0,
            disk_percent=0,
            network_io={"sent": 0, "received": 0},
            active_models=0,
            total_predictions=0,
            error_rate=0,
            avg_latency=0
        )
        self.alerts: List[Dict] = []
        self.max_history = 10000
        
    def update_model_performance(self, model_name: str, performance: ModelPerformance):
        self.model_performance[model_name] = performance
        
        for metric_name, value in [
            ("accuracy", performance.accuracy),
            ("precision", performance.precision),
            ("recall", performance.recall),
            ("f1", performance.f1),
            ("roc_auc", performance.roc_auc),
            ("latency_ms", performance.latency_ms),
            ("throughput", performance.throughput),
            ("memory_mb", performance.memory_mb)
        ]:
            self.metrics_history[f"{model_name}.{metric_name}"].append(
                MetricPoint(datetime.utcnow(), value, metric_name)
            )
            if len(self.metrics_history[f"{model_name}.{metric_name}"]) > self.max_history:
                self.metrics_history[f"{model_name}.{metric_name}"] = \
                    self.metrics_history[f"{model_name}.{metric_name}"][-self.max_history:]
    
    def add_drift_alert(self, alert: DriftAlert):
        self.drift_alerts.append(alert)
        if len(self.drift_alerts) > 1000:
            self.drift_alerts = self.drift_alerts[-1000:]
    
    def add_alert(self, alert: Dict):
        alert["timestamp"] = datetime.utcnow().isoformat()
        self.alerts.append(alert)
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]
    
    def update_system_health(self, health: SystemHealth):
        self.system_health = health
    
    def get_model_summary(self) -> List[Dict]:
        return [
            {
                "model_name": k,
                "model_type": v.model_type,
                "accuracy": v.accuracy,
                "precision": v.precision,
                "recall": v.recall,
                "f1": v.f1,
                "roc_auc": v.roc_auc,
                "latency_ms": v.latency_ms,
                "throughput": v.throughput,
                "memory_mb": v.memory_mb,
                "last_updated": v.last_updated.isoformat(),
                "training_time": v.training_time,
                "epochs": v.epochs
            }
            for k, v in self.model_performance.items()
        ]
    
    def get_metric_history(self, model_name: str, metric: str, hours: int = 24) -> List[Dict]:
        key = f"{model_name}.{metric}"
        if key not in self.metrics_history:
            return []
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        history = [
            {"timestamp": mp.timestamp.isoformat(), "value": mp.value}
            for mp in self.metrics_history[key]
            if mp.timestamp >= cutoff
        ]
        return history[-1000:]
    
    def get_drift_alerts(self, unacknowledged_only: bool = True, limit: int = 100) -> List[Dict]:
        alerts = self.drift_alerts
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        alerts = sorted(alerts, key=lambda x: x.timestamp, reverse=True)
        return [asdict(a) for a in alerts[:limit]]
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict]:
        return self.alerts[-limit:]
    
    def get_system_health(self) -> Dict:
        return asdict(self.system_health)
    
    def get_dashboard_data(self) -> Dict:
        return {
            "models": self.get_model_summary(),
            "system_health": self.get_system_health(),
            "drift_alerts": self.get_drift_alerts(),
            "recent_alerts": self.get_recent_alerts(20),
            "model_count": len(self.model_performance),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def export_performance_report(self, output_path: str = None) -> str:
        if output_path is None:
            output_path = f"performance_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "models": self.get_model_summary(),
            "system_health": self.get_system_health(),
            "drift_alerts": [asdict(a) for a in self.drift_alerts],
            "alerts": self.get_recent_alerts(100)
        }
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        return output_path


class LiveDashboard:
    def __init__(self, dashboard: PerformanceDashboard):
        self.dashboard = dashboard
        self.running = False
        self._task = None
        self.update_interval = 5
    
    async def start(self):
        self.running = True
        self._task = asyncio.create_task(self._update_loop())
    
    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
    
    async def _update_loop(self):
        while self.running:
            try:
                self._simulate_updates()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Dashboard update error: {e}")
    
    def _simulate_updates(self):
        for model_name in ["isolation_forest", "autoencoder", "lstm_autoencoder", "transformer"]:
            if model_name not in self.dashboard.model_performance:
                continue
            
            perf = self.dashboard.model_performance[model_name]
            
            perf.accuracy = min(1.0, max(0.5, perf.accuracy + random.uniform(-0.001, 0.001)))
            perf.precision = min(1.0, max(0.5, perf.precision + random.uniform(-0.001, 0.001)))
            perf.recall = min(1.0, max(0.5, perf.recall + random.uniform(-0.001, 0.001)))
            perf.f1 = min(1.0, max(0.5, perf.f1 + random.uniform(-0.001, 0.001)))
            perf.roc_auc = min(1.0, max(0.5, perf.roc_auc + random.uniform(-0.001, 0.001)))
            perf.latency_ms = max(1, perf.latency_ms + random.uniform(-0.5, 0.5))
            perf.throughput = max(10, perf.throughput + random.uniform(-1, 1))
            perf.memory_mb = max(10, perf.memory_mb + random.uniform(-0.5, 0.5))
            perf.last_updated = datetime.utcnow()
            
            self.dashboard.update_model_performance(model_name, perf)
        
        self.dashboard.system_health.cpu_percent = random.uniform(10, 40)
        self.dashboard.system_health.memory_percent = random.uniform(30, 60)
        self.dashboard.system_health.disk_percent = random.uniform(20, 50)
        self.dashboard.system_health.network_io = {
            "sent": random.uniform(1, 10),
            "received": random.uniform(1, 10)
        }
        self.dashboard.system_health.active_models = len(self.dashboard.model_performance)
        self.dashboard.system_health.total_predictions += random.randint(100, 1000)
        self.dashboard.system_health.error_rate = random.uniform(0, 0.02)
        self.dashboard.system_health.avg_latency = random.uniform(5, 20)
        
        if random.random() < 0.05:
            self.dashboard.add_drift_alert(DriftAlert(
                model_name=random.choice(list(self.dashboard.model_performance.keys())),
                drift_type=random.choice(["data_drift", "concept_drift", "prediction_drift", "feature_drift"]),
                severity=random.choice(["low", "medium", "high", "critical"]),
                metric=random.choice(["accuracy", "psi", "ks_test", "mean_shift"]),
                value=random.uniform(0.1, 0.9),
                threshold=random.uniform(0.05, 0.2),
                timestamp=datetime.utcnow()
            ))
    
    def get_dashboard_state(self) -> Dict:
        return self.dashboard.get_dashboard_data()


class DashboardAPI:
    def __init__(self, dashboard: PerformanceDashboard):
        self.dashboard = dashboard
    
    def get_model_performance(self, model_name: str = None) -> Dict:
        if model_name:
            perf = self.dashboard.model_performance.get(model_name)
            if perf:
                return asdict(perf)
            return {}
        return self.dashboard.get_model_summary()
    
    def get_metric_history(self, model_name: str, metric: str, hours: int = 24) -> List[Dict]:
        return self.dashboard.get_metric_history(model_name, metric, hours)
    
    def get_drift_alerts(self, unacknowledged_only: bool = True, limit: int = 100) -> List[Dict]:
        return self.dashboard.get_drift_alerts(unacknowledged_only, limit)
    
    def get_alerts(self, limit: int = 50) -> List[Dict]:
        return self.dashboard.get_recent_alerts(limit)
    
    def get_system_health(self) -> Dict:
        return self.dashboard.get_system_health()
    
    def get_dashboard_data(self) -> Dict:
        return self.dashboard.get_dashboard_data()
    
    def acknowledge_drift_alert(self, model_name: str, alert_index: int) -> bool:
        alerts = [a for a in self.dashboard.drift_alerts if a.model_name == model_name and not a.acknowledged]
        if 0 <= alert_index < len(alerts):
            alerts[alert_index].acknowledged = True
            return True
        return False
    
    def export_report(self, output_path: str = None) -> str:
        return self.dashboard.export_performance_report(output_path)


def create_dashboard() -> PerformanceDashboard:
    dashboard = PerformanceDashboard()
    
    models = [
        ModelPerformance(
            model_name="isolation_forest",
            model_type="Isolation Forest",
            accuracy=0.92,
            precision=0.89,
            recall=0.85,
            f1=0.87,
            roc_auc=0.94,
            latency_ms=12.5,
            throughput=8500,
            memory_mb=45,
            last_updated=datetime.utcnow(),
            training_time=45.2,
            epochs=1
        ),
        ModelPerformance(
            model_name="autoencoder",
            model_type="Autoencoder",
            accuracy=0.90,
            precision=0.87,
            recall=0.88,
            f1=0.87,
            roc_auc=0.92,
            latency_ms=8.3,
            throughput=12000,
            memory_mb=68,
            last_updated=datetime.utcnow(),
            training_time=120.5,
            epochs=50
        ),
        ModelPerformance(
            model_name="lstm_autoencoder",
            model_type="LSTM Autoencoder",
            accuracy=0.93,
            precision=0.91,
            recall=0.90,
            f1=0.90,
            roc_auc=0.95,
            latency_ms=25.8,
            throughput=4200,
            memory_mb=125,
            last_updated=datetime.utcnow(),
            training_time=320.7,
            epochs=50
        ),
        ModelPerformance(
            model_name="transformer",
            model_type="Transformer",
            accuracy=0.94,
            precision=0.92,
            recall=0.91,
            f1=0.91,
            roc_auc=0.96,
            latency_ms=42.3,
            throughput=2800,
            memory_mb=210,
            last_updated=datetime.utcnow(),
            training_time=480.3,
            epochs=100
        ),
        ModelPerformance(
            model_name="ensemble",
            model_type="Ensemble (Hybrid)",
            accuracy=0.95,
            precision=0.93,
            recall=0.92,
            f1=0.92,
            roc_auc=0.97,
            latency_ms=55.2,
            throughput=2100,
            memory_mb=320,
            last_updated=datetime.utcnow(),
            training_time=650.8,
            epochs=1
        )
    ]
    
    for model in models:
        dashboard.update_model_performance(model.model_name, model)
    
    return dashboard


def create_live_dashboard() -> LiveDashboard:
    dashboard = create_dashboard()
    return LiveDashboard(dashboard)


def create_dashboard_api() -> DashboardAPI:
    dashboard = create_dashboard()
    return DashboardAPI(dashboard)


async def run_dashboard_demo():
    live_dashboard = create_live_dashboard()
    await live_dashboard.start()
    
    try:
        while True:
            await asyncio.sleep(10)
            state = live_dashboard.get_dashboard_state()
            print(json.dumps(state, indent=2, default=str))
    except KeyboardInterrupt:
        await live_dashboard.stop()


if __name__ == "__main__":
    asyncio.run(run_dashboard_demo())