"""Data quality API: dimensions, filterable issues."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.models.station import Station
from backend.app.quality.engine import ISSUE_TYPES, fleet_quality, station_quality

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.get("/overview", summary="Fleet + per-station quality dimensions")
async def overview(hours: int = Query(default=168, ge=1, le=720),
                   db: AsyncSession = Depends(get_db)):
    return await fleet_quality(db, hours)


@router.get("/issues", summary="Filterable quality issues")
async def issues(station_id: str | None = Query(default=None),
                 parameter: str | None = Query(default=None, description="TEMPERATURE|PRESSURE|HUMIDITY|all"),
                 hours: int = Query(default=168, ge=1, le=720),
                 issue_type: str | None = Query(default=None),
                 limit: int = Query(default=200, ge=1, le=1000),
                 db: AsyncSession = Depends(get_db)):
    if issue_type is not None and issue_type not in ISSUE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown issue_type; one of {', '.join(ISSUE_TYPES)}")
    if parameter is not None and parameter not in ("TEMPERATURE", "PRESSURE", "HUMIDITY", "all"):
        raise HTTPException(status_code=400, detail="parameter must be TEMPERATURE|PRESSURE|HUMIDITY|all")
    if station_id is not None and await db.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
    from collections import Counter as _Counter

    from sqlalchemy import select as _select

    stations = [station_id] if station_id else [
        s.station_id for s in (await db.execute(_select(Station))).scalars().all()
        if s.station_id != "SYSTEM"]
    out = []
    for sid in stations:
        _, iss = await station_quality(db, sid, hours)
        out.extend(iss)
    unfiltered_counts = dict(_Counter(i["issue_type"] for i in out))
    if parameter is not None:
        out = [i for i in out if parameter in i["parameter"].split(",")]
    if issue_type is not None:
        out = [i for i in out if i["issue_type"] == issue_type]
    out.sort(key=lambda i: i["timestamp"], reverse=True)
    return {"total": len(out), "issues": out[:limit],
            "known_issue_types": list(ISSUE_TYPES),
            "note": "unfiltered counts: " + str(unfiltered_counts)}
