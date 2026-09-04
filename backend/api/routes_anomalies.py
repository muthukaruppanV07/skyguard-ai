from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from backend.database.session import get_db
from backend.database.repositories import AnomalyRepository
from backend.schemas.anomaly import AnomalyResponse, AnomalyDetailResponse
from backend.models.anomaly import AnomalySeverity

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("", response_model=list[AnomalyResponse])
async def list_anomalies(
    station_id: str | None = Query(None),
    severity: AnomalySeverity | None = Query(None),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    repo = AnomalyRepository(db)
    anomalies = await repo.get_recent(station_id, severity, hours, limit)
    return [AnomalyResponse.model_validate(a) for a in anomalies]


@router.get("/{anomaly_id}", response_model=AnomalyDetailResponse)
async def get_anomaly(anomaly_id: int, db: AsyncSession = Depends(get_db)):
    repo = AnomalyRepository(db)
    anomaly = await repo.get_by_id(anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return AnomalyDetailResponse.model_validate(anomaly)