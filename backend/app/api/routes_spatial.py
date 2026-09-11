"""Spatial intelligence API: neighbours, agreement, deviation, regional consistency."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.spatial.intel import get_spatial_intel, overview_latest

router = APIRouter(prefix="/spatial", tags=["spatial"])


def _to_dict(intel) -> dict:
    return {
        "station_id": intel.station_id,
        "timestamp": intel.timestamp,
        "neighbors": [
            {"station_id": n.station_id, "name": n.name, "distance_km": n.distance_km,
             "temperature": n.temperature, "pressure": n.pressure, "humidity": n.humidity,
             "temp_deviation": n.temp_deviation}
            for n in intel.neighbors
        ],
        "neighbor_agreement": intel.neighbor_agreement,
        "spatial_deviation_c": intel.spatial_deviation_c,
        "spatial_z": intel.spatial_z,
        "neighbor_mean_c": intel.neighbor_mean_c,
        "regional_consistency": intel.regional_consistency,
        "regional_band": intel.regional_band,
        "classification_hint": intel.classification_hint,
        "method": intel.method,
    }


@router.get("/overview", summary="Latest reading per station for map overlays")
async def spatial_overview(db: AsyncSession = Depends(get_db)):
    return await overview_latest(db)


@router.get("/{station_id}", summary="Spatial intel for one station")
async def spatial_station(
    station_id: str,
    radius_km: float = Query(default=2000.0, ge=1, le=20000),
    k: int = Query(default=4, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    try:
        intel = await get_spatial_intel(db, station_id, radius_km, k)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_dict(intel)
