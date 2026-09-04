from pydantic import BaseModel, ConfigDict
from datetime import datetime
from backend.models.anomaly import AnomalySeverity, RootCause


class AnomalyResponse(BaseModel):
    id: int
    reading_id: int
    station_id: str
    timestamp: datetime
    anomaly_score: float
    confidence: float
    severity: AnomalySeverity
    root_cause: RootCause
    model_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnomalyDetailResponse(AnomalyResponse):
    rule_score: float
    if_score: float
    ae_score: float
    temporal_score: float
    multivariate_score: float
    spatial_score: float
    observed_temp: float
    observed_pressure: float
    observed_humidity: float
    expected_temp: float | None
    expected_pressure: float | None
    expected_humidity: float | None
    correction_confidence: float
    explanation: str | None
    contributing_factors: str | None