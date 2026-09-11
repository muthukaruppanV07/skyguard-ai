"""Pydantic schemas with strict T/P/H validation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.core.config import settings

StationStatus = Literal["ACTIVE", "MAINTENANCE", "OFFLINE"]


class StationOut(BaseModel):
    station_id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    status: str

    model_config = {"from_attributes": True}


class ObservationIn(BaseModel):
    station_id: str = Field(min_length=1, max_length=20)
    timestamp: datetime
    temperature: float = Field(ge=settings.TEMP_MIN, le=settings.TEMP_MAX)
    pressure: float = Field(ge=settings.PRESSURE_MIN, le=settings.PRESSURE_MAX)
    humidity: float = Field(ge=settings.HUMIDITY_MIN, le=settings.HUMIDITY_MAX)


class ObservationOut(BaseModel):
    """Stored readings: no range gates here — anomalous values must remain readable."""

    id: int
    station_id: str
    timestamp: datetime
    temperature: float
    pressure: float
    humidity: float

    model_config = {"from_attributes": True}


class AnomalyOut(BaseModel):
    id: int
    station_id: str
    observation_id: int | None
    timestamp: datetime
    score: float
    severity: str
    root_cause: str
    message: str
    confidence: float
    resolved: bool = False

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    station_id: str
    anomaly_id: int | None
    severity: str
    message: str
    acknowledged: bool
    muted: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class SensorHealthOut(BaseModel):
    id: int
    station_id: str
    sensor_type: str
    score: float
    status: str
    anomaly_count: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class SensorScoreOut(BaseModel):
    sensor_type: str
    score: float
    status: str
    anomaly_count: int
    penalties: dict


class StationHealthSummaryOut(BaseModel):
    station_id: str
    overall: float
    status: str
    worst_sensor: str
    sensors: list[SensorScoreOut]


class StationHealthDetailOut(StationHealthSummaryOut):
    trend: list[dict]


class MaintenanceIntelOut(BaseModel):
    station_id: str
    sensor_type: str
    health: float
    health_status: str
    maintenance_risk: float
    risk_level: str
    maintenance_priority: str
    reason: str
    recommended_action: list[str]
    signals: dict


class StationMaintenanceOut(BaseModel):
    station_id: str
    worst_risk: float
    worst_sensor: str
    sensors: list[MaintenanceIntelOut]
    open_orders: list[dict]


class ErrorOut(BaseModel):
    detail: str
