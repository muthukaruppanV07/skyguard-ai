"""Required foundation endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.models.alert import Alert
from backend.app.models.anomaly import Anomaly
from backend.app.models.observation import Observation
from backend.app.models.station import Station
from backend.app.schemas.schemas import (
    AlertOut,
    AnomalyOut,
    ObservationIn,
    ObservationOut,
    StationHealthDetailOut,
    StationHealthSummaryOut,
    StationOut,
)
from backend.app.services.observation_service import create_observation

router = APIRouter()


@router.get("/stations", response_model=list[StationOut], summary="List all AWS stations")
async def list_stations(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Station).where(Station.station_id != "SYSTEM").order_by(Station.station_id))).scalars().all()
    return rows


@router.get("/stations/{station_id}", response_model=StationOut, summary="Station details")
async def get_station(station_id: str, db: AsyncSession = Depends(get_db)):
    station = await db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
    return station


@router.get("/observations", response_model=list[ObservationOut], summary="Paginated observations")
async def list_observations(
    station_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Observation).order_by(desc(Observation.timestamp)).limit(limit)
    if station_id:
        stmt = stmt.where(Observation.station_id == station_id)
    return (await db.execute(stmt)).scalars().all()


@router.post("/observations", response_model=ObservationOut, status_code=201, summary="Ingest one observation")
async def post_observation(payload: ObservationIn, db: AsyncSession = Depends(get_db)):
    try:
        obs, _ = await create_observation(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return obs


@router.get("/anomalies", response_model=list[AnomalyOut], summary="Paginated anomalies")
async def list_anomalies(
    station_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Anomaly).order_by(desc(Anomaly.timestamp)).limit(limit)
    if station_id:
        stmt = stmt.where(Anomaly.station_id == station_id)
    return (await db.execute(stmt)).scalars().all()


@router.get("/sensor-health", response_model=list[StationHealthSummaryOut], summary="Health overview per station")
async def list_sensor_health(db: AsyncSession = Depends(get_db)):
    from backend.app.health.engine import compute_station_health

    stations = (await db.execute(select(Station).where(Station.station_id != "SYSTEM").order_by(Station.station_id))).scalars().all()
    out = []
    for st in stations:
        snap = await compute_station_health(db, st.station_id)
        worst = min(snap.sensors, key=lambda s: s.score)
        out.append({
            "station_id": snap.station_id,
            "overall": snap.overall,
            "status": snap.status,
            "worst_sensor": worst.sensor_type,
            "sensors": [s.__dict__ for s in snap.sensors],
        })
    return out


@router.get("/sensor-health/{station_id}", response_model=StationHealthDetailOut, summary="Per-sensor health + factors + trend")
async def get_sensor_health(station_id: str, db: AsyncSession = Depends(get_db)):
    from backend.app.health.engine import compute_station_health, health_trend

    if await db.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
    snap = await compute_station_health(db, station_id)
    worst = min(snap.sensors, key=lambda s: s.score)
    trend = await health_trend(db, station_id)
    return {
        "station_id": snap.station_id,
        "overall": snap.overall,
        "status": snap.status,
        "worst_sensor": worst.sensor_type,
        "sensors": [s.__dict__ for s in snap.sensors],
        "trend": trend,
    }


@router.get("/alerts", response_model=list[AlertOut], summary="Operator alerts", include_in_schema=True)
async def list_alerts(
    station_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    if station_id:
        stmt = stmt.where(Alert.station_id == station_id)
    return (await db.execute(stmt)).scalars().all()


@router.patch("/alerts/{alert_id}", response_model=AlertOut, summary="Acknowledge or mute an alert")
async def acknowledge_alert(alert_id: int, payload: dict, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    if "acknowledged" in payload:
        alert.acknowledged = bool(payload["acknowledged"])
    if "muted" in payload:
        alert.muted = bool(payload["muted"])
    await db.commit()
    await db.refresh(alert)
    return alert


@router.patch("/anomalies/{anomaly_id}/resolve", response_model=AnomalyOut, summary="Mark anomaly resolved")
async def resolve_anomaly(anomaly_id: int, db: AsyncSession = Depends(get_db)):
    anomaly = await db.get(Anomaly, anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    anomaly.resolved = True
    # anomaly_id stays NULL: one detection alert per anomaly (UNIQUE); this is a workflow notice.
    db.add(Alert(station_id=anomaly.station_id, anomaly_id=None, severity="INFO",
                 message=f"{anomaly.station_id}: {anomaly.anomaly_type} (#{anomaly.id}) resolved by operator"))
    await db.commit()
    await db.refresh(anomaly)
    return anomaly
