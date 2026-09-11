"""Spatial intelligence: neighbor agreement, deviation, regional consistency.

All metrics derive from live readings + histories. Bands are fixed,
documented thresholds applied to computed numbers — never canned verdicts:

- Neighbor agreement from |z| of the station vs the neighbour group mean:
  HIGH (|z|<=1.5) | MEDIUM (|z|<=3) | LOW (above) | UNKNOWN (<2 neighbours).
- Regional consistency = share of neighbours that are THEMSELVES unusual
  (vs their own histories) in the same direction:
  HIGH (>=0.50) | MEDIUM (>=0.25) | LOW (below) | UNKNOWN (<2 scored).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.app.detection import features as F
from backend.app.detection.event_classifier import haversine_km
from backend.app.models.observation import Observation
from backend.app.models.station import Station

TEMP_FLOOR = 0.5  # neighbour-group std floor (C); identical convention as classifier


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


@dataclass
class NeighborIntel:
    station_id: str
    name: str
    distance_km: float
    temperature: float | None
    pressure: float | None
    humidity: float | None
    temp_deviation: float | None  # vs neighbour-group mean


@dataclass
class SpatialIntel:
    station_id: str
    timestamp: str | None = None
    neighbors: list = field(default_factory=list)
    neighbor_agreement: str = "UNKNOWN"
    spatial_deviation_c: float | None = None
    spatial_z: float | None = None
    neighbor_mean_c: float | None = None
    regional_consistency: float | None = None
    regional_band: str = "UNKNOWN"
    classification_hint: str = ""
    method: dict = field(default_factory=dict)


def agreement_band(z: float | None, n: int) -> str:
    if z is None or n < 2:
        return "UNKNOWN"
    az = abs(z)
    if az <= 1.5:
        return "HIGH"
    if az <= 3.0:
        return "MEDIUM"
    return "LOW"


def regional_band(frac: float | None, n: int) -> str:
    if frac is None or n < 2:
        return "UNKNOWN"
    if frac >= 0.50:
        return "HIGH"
    if frac >= 0.25:
        return "MEDIUM"
    return "LOW"


def compute_intel(
    station_id: str,
    current: dict,
    neighbors: list[dict],
    neighbor_histories: dict[str, list[dict]] | None = None,
) -> SpatialIntel:
    """Pure computation over live readings (+ optional neighbour histories)."""
    neighbor_histories = neighbor_histories or {}
    temps = [(n.get("station_id"), n.get("temperature")) for n in neighbors]
    temps = [(sid, t) for sid, t in temps if not _missing(t)]
    v = current.get("temperature")

    intel = SpatialIntel(station_id=station_id, timestamp=current.get("timestamp"))
    if _missing(v) or len(temps) < 2:
        intel.method = {"note": "need station value + >=2 neighbours with data"}
        intel.classification_hint = "Spatial check inconclusive: too few neighbours with data."
        return intel

    vals = [t for _, t in temps]
    mean = sum(vals) / len(vals)
    std = math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals))
    z = (v - mean) / max(std, TEMP_FLOOR)
    dev = v - mean

    intel.neighbor_mean_c = round(mean, 2)
    intel.spatial_deviation_c = round(dev, 2)
    intel.spatial_z = round(z, 2)
    intel.neighbor_agreement = agreement_band(z, len(vals))
    intel.neighbors = [
        NeighborIntel(
            station_id=n.get("station_id", ""),
            name=n.get("name", n.get("station_id", "")),
            distance_km=round(n.get("distance_km", 0.0), 1),
            temperature=n.get("temperature"),
            pressure=n.get("pressure"),
            humidity=n.get("humidity"),
            temp_deviation=round(t - mean, 2),
        )
            for n, t in zip([x for x in neighbors if not _missing(x.get("temperature"))], vals)
    ]

    # Regional consistency: neighbours unusual vs their OWN histories.
    scored = same = 0
    for n in neighbors:
        sid = n.get("station_id", "")
        nh = neighbor_histories.get(sid, [])
        if len(nh) < 6 or _missing(n.get("temperature")):
            continue
        try:
            nf = F.compute_latest([*nh, {**{k: n.get(k) for k in ("temperature", "pressure", "humidity")},
                                         "timestamp": current["timestamp"]}])
        except (ValueError, KeyError):
            continue
        hd = nf.get("temperature_historical_deviation")
        if hd is None or (isinstance(hd, float) and math.isnan(hd)):
            continue
        scored += 1
        own_sign = 1 if dev >= 0 else -1
        if abs(hd) >= 2.0 and (1 if hd >= 0 else -1) == own_sign:
            same += 1
    frac = (same / scored) if scored >= 2 else None
    intel.regional_consistency = round(frac, 3) if frac is not None else None
    intel.regional_band = regional_band(frac, scored)
    intel.method = {"scored_neighbours": scored, "same_direction": same,
                    "group_std": round(std, 2), "n_neighbours": len(vals)}

    if intel.regional_band == "HIGH":
        intel.classification_hint = (
            f"HIGH regional consistency ({same}/{scored} neighbours share the move): "
            "favours PROBABLE_WEATHER_EVENT in the classifier."
        )
    elif intel.neighbor_agreement == "LOW":
        intel.classification_hint = (
            f"Isolated anomaly ({dev:+.1f}C vs neighbours): favours PROBABLE_SENSOR_FAULT."
        )
    else:
        intel.classification_hint = "Mixed spatial evidence: classifier decides on full fusion."
    return intel


async def get_spatial_intel(
    session,
    station_id: str,
    radius_km: float = 500.0,
    k: int = 4,
    history_limit: int = 48,
) -> SpatialIntel:
    """Load latest readings + histories from the DB and compute intel."""
    from sqlalchemy import desc, select

    stations = (await session.execute(select(Station))).scalars().all()
    target = next((s for s in stations if s.station_id == station_id), None)
    if target is None:
        raise ValueError(f"Unknown station_id: {station_id}")
    cands = [
        s for s in stations if s.station_id != station_id and s.station_id != "SYSTEM"
        and haversine_km(target.latitude, target.longitude, s.latitude, s.longitude) <= radius_km
    ]
    cands.sort(key=lambda s: haversine_km(target.latitude, target.longitude, s.latitude, s.longitude))
    cands = cands[: max(0, k)]

    async def latest(sid: str):
        stmt = (select(Observation).where(Observation.station_id == sid)
                .order_by(desc(Observation.timestamp)).limit(1))
        return (await session.execute(stmt)).scalars().first()

    async def hist(sid: str):
        stmt = (select(Observation).where(Observation.station_id == sid)
                .order_by(desc(Observation.timestamp)).limit(history_limit))
        rows = (await session.execute(stmt)).scalars().all()
        return [{"timestamp": o.timestamp, "temperature": o.temperature,
                 "pressure": o.pressure, "humidity": o.humidity} for o in reversed(rows)]

    me = await latest(station_id)
    if me is None:
        intel = SpatialIntel(station_id=station_id)
        intel.method = {"note": "station has no observations yet"}
        intel.classification_hint = "Spatial check inconclusive: station has no readings."
        return intel
    current = {"timestamp": me.timestamp.isoformat() if hasattr(me.timestamp, "isoformat") else str(me.timestamp),
               "temperature": me.temperature, "pressure": me.pressure, "humidity": me.humidity}
    neighbors, histories = [], {}
    for s in cands:
        o = await latest(s.station_id)
        if o is None:
            continue
        d = haversine_km(target.latitude, target.longitude, s.latitude, s.longitude)
        neighbors.append({"station_id": s.station_id, "name": s.name, "distance_km": d,
                          "temperature": o.temperature, "pressure": o.pressure, "humidity": o.humidity})
        histories[s.station_id] = await hist(s.station_id)
    return compute_intel(station_id, current, neighbors, histories)


async def overview_latest(session) -> list[dict]:
    """Latest reading per station (for map overlays)."""
    from sqlalchemy import desc, select

    stations = (await session.execute(select(Station).where(Station.station_id != "SYSTEM").order_by(Station.station_id))).scalars().all()
    out = []
    for s in stations:
        stmt = (select(Observation).where(Observation.station_id == s.station_id)
                .order_by(desc(Observation.timestamp)).limit(1))
        o = (await session.execute(stmt)).scalars().first()
        out.append({"station_id": s.station_id, "name": s.name,
                    "latitude": s.latitude, "longitude": s.longitude, "status": s.status,
                    "temperature": o.temperature if o else None,
                    "timestamp": o.timestamp.isoformat() if o and hasattr(o.timestamp, "isoformat") else None})
    return out
