from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from backend.models.station import StationStatus


class StationBase(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    elevation: float
    status: StationStatus
    created_at: datetime


class StationResponse(StationBase):
    model_config = ConfigDict(from_attributes=True)


class StationDetailResponse(StationBase):
    latest_temperature: Optional[float] = None
    latest_pressure: Optional[float] = None
    latest_humidity: Optional[float] = None
    latest_timestamp: Optional[datetime] = None
    anomaly_score: Optional[float] = None
    severity: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)