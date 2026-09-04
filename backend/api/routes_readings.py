from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from backend.database.session import get_db
from backend.database.repositories import ReadingRepository
from backend.schemas.reading import ReadingResponse

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("", response_model=list[ReadingResponse])
async def list_readings(
    station_id: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    repo = ReadingRepository(db)
    if station_id and start and end:
        readings = await repo.get_by_station_time_range(station_id, start, end, limit)
    else:
        readings = await repo.get_latest_all_stations()
    return [ReadingResponse.model_validate(r) for r in readings]