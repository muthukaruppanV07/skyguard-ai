from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.database.repositories import SensorHealthRepository, StationRepository
from backend.schemas.health import NetworkHealthResponse, StationHealthResponse
from backend.models.sensor_health import SensorType

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=NetworkHealthResponse)
async def get_network_health(db: AsyncSession = Depends(get_db)):
    repo = SensorHealthRepository(db)
    summary = await repo.get_network_summary()
    return NetworkHealthResponse(**summary)


@router.get("/{station_id}", response_model=StationHealthResponse)
async def get_station_health(station_id: str, db: AsyncSession = Depends(get_db)):
    station_repo = StationRepository(db)
    station = await station_repo.get_by_id(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    health_repo = SensorHealthRepository(db)
    health_records = await health_repo.get_by_station(station_id)
    
    return StationHealthResponse(
        station_id=station_id,
        station_name=station.name,
        sensors={h.sensor_type.value: {
            "score": h.health_score,
            "status": h.status.value,
            "anomaly_count_24h": h.anomaly_count_24h,
            "anomaly_count_7d": h.anomaly_count_7d,
            "drift_detected": h.drift_detected,
            "frozen_count": h.frozen_count,
            "missing_count": h.missing_count,
            "comm_failure_count": h.comm_failure_count,
            "reconstruction_error_avg": h.reconstruction_error_avg,
        } for h in health_records},
        overall_score=sum(h.health_score for h in health_records) / len(health_records) if health_records else 0,
    )