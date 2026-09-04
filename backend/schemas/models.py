from pydantic import BaseModel, ConfigDict
from typing import Dict, Any
from datetime import datetime


class ModelInfoResponse(BaseModel):
    model_name: str
    model_version: str
    metrics: Dict[str, Any]
    trained_at: datetime

    model_config = ConfigDict(from_attributes=True)