from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.database.repositories import AnomalyRepository, StationRepository, SensorHealthRepository
from backend.schemas.statistics import StatisticsResponse
from backend.models.anomaly import AnomalySeverity

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("", response_model=StatisticsResponse)
async def get_statistics(hours: int = 24, db: AsyncSession = Depends(get_db)):
    anomaly_repo = AnomalyRepository(db)
    station_repo = StationRepository(db)
    health_repo = SensorHealthRepository(db)
    
    stats = await anomaly_repo.get_statistics(hours)
    stations = await station_repo.get_active()
    health_summary = await health_repo.get_network_summary()
    
    healthy = 0
    warning = 0
    critical = 0
    for station_health in health_summary.get("stations", {}).values():
        for sensor_health in station_health.values():
            score = sensor_health.get("score", 100)
            if score >= 80:
                healthy += 1
            elif score >= 60:
                warning += 1
            else:
                critical += 1
    
    return StatisticsResponse(
        total_stations=len(stations),
        healthy_stations=healthy,
        warning_stations=warning,
        critical_stations=critical,
        active_anomalies=stats["total"],
        avg_network_health=health_summary.get("overall_avg", 0),
        anomaly_breakdown=stats,
    )