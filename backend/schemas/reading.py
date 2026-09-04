from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ReadingResponse(BaseModel):
    id: int
    station_id: str
    timestamp: datetime
    temperature: float
    pressure: float
    humidity: float
    is_valid: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)