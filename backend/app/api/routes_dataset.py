"""Dataset APIs: configurable generation + CSV upload."""

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.services.dataset_service import ingest_csv
from backend.app.services.observation_service import create_observation
from backend.app.schemas.schemas import ObservationIn
from backend.app.simulation.dataset_generator import (
    GeneratorConfig,
    generate_dataset,
    label_histogram,
    rows_to_dicts,
)

router = APIRouter(prefix="/dataset", tags=["dataset"])


class GenerateRequest(BaseModel):
    num_stations: int = Field(default=4, ge=1, le=8)
    num_observations: int = Field(default=1000, ge=10, le=50000)
    sampling_interval_minutes: int = Field(default=60, ge=1, le=1440)
    anomaly_percentage: float = Field(default=5.0, ge=0, le=50)
    seed: int = Field(default=42)
    ingest: bool = Field(default=False, description="Also insert clean rows into DB")


@router.post("/generate", summary="Generate realistic synthetic labelled dataset")
async def generate(
    req: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    station_table = [
        {"station_id": s["station_id"], "latitude": s["latitude"], "longitude": s["longitude"]}
        for s in settings.STATION_COORDS
    ]
    try:
        rows = generate_dataset(
            GeneratorConfig(
                num_stations=req.num_stations,
                num_observations=req.num_observations,
                sampling_interval_minutes=req.sampling_interval_minutes,
                anomaly_percentage=req.anomaly_percentage,
                seed=req.seed,
                start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            station_table,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ingested = 0
    if req.ingest:
        for r in rows:
            if r.temperature is None:
                continue
            try:
                await create_observation(
                    db,
                    ObservationIn(
                        station_id=r.station_id,
                        timestamp=r.timestamp,
                        temperature=r.temperature,
                        pressure=r.pressure,
                        humidity=r.humidity,
                    ),
                )
                ingested += 1
            except ValueError:
                continue  # unknown station etc. — preview still returned

    preview = rows_to_dicts(rows[:5], labelled=True)
    return {
        "total_rows": len(rows),
        "labels": label_histogram(rows),
        "ingested": ingested,
        "preview": preview,
    }


@router.post("/upload", summary="Upload CSV: timestamp,station_id,latitude,longitude,temperature,pressure,humidity")
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files accepted")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    try:
        result = await ingest_csv(db, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"filename": file.filename, **result}


@router.get("/template", summary="Download blank CSV template")
async def template():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "station_id", "latitude", "longitude", "temperature", "pressure", "humidity"])
    w.writerow(["2026-01-01T00:00:00+00:00", "AWS001", 28.6139, 77.2090, 31.5, 1005.2, 62.0])
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(buf.getvalue(), media_type="text/csv")
