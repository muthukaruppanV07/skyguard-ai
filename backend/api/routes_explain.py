from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.database.repositories import AnomalyRepository
from backend.schemas.explanation import ExplanationResponse

router = APIRouter(prefix="/explanation", tags=["explainability"])


@router.get("/{anomaly_id}", response_model=ExplanationResponse)
async def get_explanation(anomaly_id: int, db: AsyncSession = Depends(get_db)):
    repo = AnomalyRepository(db)
    anomaly = await repo.get_by_id(anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    
    return ExplanationResponse(
        anomaly_id=anomaly.id,
        explanation=anomaly.explanation,
        contributing_factors=anomaly.contributing_factors,
        shap_values={},
        confidence=anomaly.confidence,
    )