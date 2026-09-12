"""Re-export all models so metadata registers on init_db import."""

from backend.app.models.alert import Alert
from backend.app.models.anomaly import Anomaly
from backend.app.models.maintenance import MaintenanceRecommendation
from backend.app.models.model_result import ModelResult
from backend.app.models.observation import Observation
from backend.app.models.report_run import ReportRun
from backend.app.models.sensor_health import SensorHealth
from backend.app.models.station import Station

__all__ = [
    "Alert",
    "Anomaly",
    "MaintenanceRecommendation",
    "ModelResult",
    "Observation",
    "ReportRun",
    "SensorHealth",
    "Station",
]
