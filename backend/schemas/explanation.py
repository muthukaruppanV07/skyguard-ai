from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, List


class ExplanationResponse(BaseModel):
    anomaly_id: int
    explanation: str
    contributing_factors: str
    shap_values: Dict[str, Any]
    confidence: float

    model_config = ConfigDict(from_attributes=True)