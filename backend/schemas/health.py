from pydantic import BaseModel, ConfigDict
from typing import Dict, Any


class NetworkHealthResponse(BaseModel):
    stations: Dict[str, Any]
    overall_avg: float

    model_config = ConfigDict(from_attributes=True)


class StationHealthResponse(BaseModel):
    station_id: str
    station_name: str
    sensors: Dict[str, Any]
    overall_score: float

    model_config = ConfigDict(from_attributes=True)