"""Maintenance APIs: per-sensor risk intel + persisted work orders."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.health.maintenance import analyze_station, sync_recommendations
from backend.app.models.maintenance import MaintenanceRecommendation
from backend.app.models.station import Station
from backend.app.schemas.schemas import MaintenanceIntelOut, StationMaintenanceOut

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def _intel_to_dict(item) -> dict:
    return {
        "station_id": item.station_id,
        "sensor_type": item.sensor_type,
        "health": item.health,
        "health_status": item.health_status,
        "maintenance_risk": item.maintenance_risk,
        "risk_level": item.risk_level,
        "maintenance_priority": item.maintenance_priority,
        "reason": item.reason,
        "recommended_action": item.recommended_action,
        "signals": item.signals,
    }


async def _open_orders(db: AsyncSession, station_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(MaintenanceRecommendation)
            .where(MaintenanceRecommendation.station_id == station_id,
                   MaintenanceRecommendation.status == "OPEN")
            .order_by(MaintenanceRecommendation.id)
        )
    ).scalars().all()
    return [{"id": r.id, "priority": r.priority, "recommendation": r.recommendation,
             "reason": r.reason, "status": r.status} for r in rows]


@router.get("", response_model=list[StationMaintenanceOut], summary="Worst-sensor risk per station")
async def list_maintenance(db: AsyncSession = Depends(get_db)):
    stations = (await db.execute(select(Station).where(Station.station_id != "SYSTEM").order_by(Station.station_id))).scalars().all()
    out = []
    for st in stations:
        intel = await analyze_station(db, st.station_id)
        worst = max(intel, key=lambda i: i.maintenance_risk)
        out.append({"station_id": st.station_id, "worst_risk": worst.maintenance_risk,
                    "worst_sensor": worst.sensor_type,
                    "sensors": [_intel_to_dict(i) for i in intel],
                    "open_orders": await _open_orders(db, st.station_id)})
    return out


@router.get("/{station_id}", response_model=StationMaintenanceOut, summary="Per-sensor maintenance intel")
async def get_maintenance(station_id: str, db: AsyncSession = Depends(get_db)):
    if await db.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
    intel = await analyze_station(db, station_id)
    worst = max(intel, key=lambda i: i.maintenance_risk)
    return {"station_id": station_id, "worst_risk": worst.maintenance_risk,
            "worst_sensor": worst.sensor_type,
            "sensors": [_intel_to_dict(i) for i in intel],
            "open_orders": await _open_orders(db, station_id)}


@router.post("/{station_id}/sync", response_model=StationMaintenanceOut, summary="Recompute intel and upsert work orders")
async def sync_maintenance(station_id: str, db: AsyncSession = Depends(get_db)):
    if await db.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
    intel = await sync_recommendations(db, station_id)
    await db.commit()
    worst = max(intel, key=lambda i: i.maintenance_risk)
    return {"station_id": station_id, "worst_risk": worst.maintenance_risk,
            "worst_sensor": worst.sensor_type,
            "sensors": [_intel_to_dict(i) for i in intel],
            "open_orders": await _open_orders(db, station_id)}
