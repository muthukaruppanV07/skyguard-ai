from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.services.ingestion import IngestionService
from backend.database.repositories import ReadingRepository

router = APIRouter(prefix="/detect", tags=["detection"])


@router.post("")
async def trigger_detection(db: AsyncSession = Depends(get_db)):
    reading_repo = ReadingRepository(db)
    ingestion = IngestionService(db)
    
    latest_readings = await reading_repo.get_latest_all_stations()
    
    results = []
    for reading in latest_readings:
        result = await ingestion.process_reading(reading)
        results.append({
            "station_id": reading.station_id,
            "reading_id": reading.id,
            "result": result,
        })
    
    return {"processed": len(results), "results": results}