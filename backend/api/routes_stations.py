from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.database.repositories import StationRepository
from backend.schemas.station import StationResponse, StationDetailResponse

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=list[StationResponse])
async def list_stations(db: AsyncSession = Depends(get_db)):
    repo = StationRepository(db)
    stations = await repo.get_all()
    return [StationResponse.model_validate(s) for s in stations]


@router.get("/{station_id}", response_model=StationDetailResponse)
async def get_station(station_id: str, db: AsyncSession = Depends(get_db)):
    repo = StationRepository(db)
    station = await repo.get_by_id(station_id)
    if not station:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Station not found")
    return StationDetailResponse.model_validate(station)