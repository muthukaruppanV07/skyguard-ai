from pydantic import BaseModel, ConfigDict
from typing import Dict, Any


class StatisticsResponse(BaseModel):
    total_stations: int
    healthy_stations: int
    warning_stations: int
    critical_stations: int
    active_anomalies: int
    avg_network_health: float
    anomaly_breakdown: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)