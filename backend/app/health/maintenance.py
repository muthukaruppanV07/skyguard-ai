"""Predictive maintenance intelligence: risk from measured degradation.

Six trend signals compare the recent half of the window against the older
half (plus health then-vs-now). Every signal is a counted/measured delta;
minimum-evidence gates make weak histories abstain (0.0) instead of
guessing. Same history in -> same risk out, always.

Deliberately absent: failure dates. Nothing here fits a survival model,
so no ETA is claimed — only risk level, priority, reason and actions.

Risk = 100 x weighted mean of the six signals (weights sum to 1.0):
  anomaly frequency trend  .20 | drift trend            .20
  repeated failures        .15 | health decline         .20
  missing-data trend       .10 | comm instability       .15
Levels: HIGH (>=60) | MEDIUM (>=35) | LOW (<35).
Priority: URGENT (HIGH + critical health or active comm faults),
  HIGH, MEDIUM, LOW (LOW raises no work order, intel only).
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.health.engine import (
    DRIFT_LIMIT_PER_DAY,
    FIELD,
    SENSORS,
    _slope_per_day,
    _utc,
    compute_station_health,
    implicated_sensors,
)
from backend.app.models.anomaly import Anomaly
from backend.app.models.maintenance import MaintenanceRecommendation
from backend.app.models.observation import Observation

SIGNAL_WEIGHTS = {
    "frequency_up": 0.20,
    "drift_up": 0.20,
    "repeated": 0.15,
    "decline": 0.20,
    "missing_up": 0.10,
    "comm": 0.15,
}

UNIT = {"TEMPERATURE": "C", "PRESSURE": "hPa", "HUMIDITY": "%"}

BASE_ACTIONS = {
    "TEMPERATURE": [
        "Inspect the temperature probe and its radiation shield",
        "Verify calibration against a reference instrument",
        "Compare recent readings against neighbouring stations",
        "Check exposure: new heat sources, shading or ventilation changes",
    ],
    "PRESSURE": [
        "Inspect the barometer port for blockages or moisture",
        "Verify calibration against a reference barometer",
        "Check temperature compensation behaviour",
        "Review recent pressure jumps against neighbouring stations",
    ],
    "HUMIDITY": [
        "Inspect the humidity probe for contamination or saturation",
        "Clean or replace the filter cap",
        "Verify calibration against a reference instrument",
        "Check for water ingress around the sensor housing",
    ],
}

SIGNAL_ACTIONS = {
    "frequency_up": "Rising fault rate: prioritise this sensor on the next site visit",
    "drift_up": "Schedule recalibration; drift is accelerating",
    "repeated": "Same failure keeps recurring: consider replacing the sensor rather than resetting it",
    "decline": "Health is on a downward path: do not defer the visit",
    "missing_up": "Check power supply and telemetry link stability",
    "comm": "Check modem, antenna alignment and SIM/data plan; inspect logger memory as backfill source",
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class SensorMaintenance:
    station_id: str
    sensor_type: str
    health: float
    health_status: str
    maintenance_risk: float
    risk_level: str
    maintenance_priority: str
    reason: str
    recommended_action: list = field(default_factory=list)
    signals: dict = field(default_factory=dict)


def _miss_rate(obs, median_min: float) -> float:
    if len(obs) < 2 or not median_min:
        return 0.0
    ts = sorted(_utc(o.timestamp) for o in obs)
    span_min = (ts[-1] - ts[0]).total_seconds() / 60.0
    expected = max(1.0, span_min / median_min + 1)
    return max(0.0, 1.0 - len(obs) / expected)


def _median_cadence(obs) -> float:
    if len(obs) < 3:
        return 0.0
    ts = sorted(_utc(o.timestamp) for o in obs)
    gaps = [(b - a).total_seconds() / 60.0 for a, b in zip(ts, ts[1:]) if (b - a).total_seconds() > 0]
    return statistics.median(gaps) if gaps else 0.0


async def analyze_station(
    session: AsyncSession,
    station_id: str,
    window_days: float = 30.0,
    end: datetime | None = None,
) -> list[SensorMaintenance]:
    """Per-sensor maintenance intel over the trailing window."""
    end = _utc(end or datetime.now(timezone.utc))
    start = end - timedelta(days=window_days)
    mid = start + (end - start) / 2

    obs = (
        await session.execute(
            select(Observation)
            .where(Observation.station_id == station_id,
                   Observation.timestamp >= start.replace(tzinfo=None),
                   Observation.timestamp <= end.replace(tzinfo=None))
            .order_by(Observation.timestamp)
        )
    ).scalars().all()
    obs = list(obs)
    anoms = (
        await session.execute(
            select(Anomaly)
            .where(Anomaly.station_id == station_id,
                   Anomaly.timestamp >= start.replace(tzinfo=None),
                   Anomaly.timestamp <= end.replace(tzinfo=None))
            .order_by(Anomaly.timestamp)
        )
    ).scalars().all()
    anoms = list(anoms)

    now_snap = await compute_station_health(session, station_id, window_days, end)
    then_snap = await compute_station_health(session, station_id, window_days, mid)
    now_by = {s.sensor_type: s for s in now_snap.sensors}
    then_by = {s.sensor_type: s for s in then_snap.sensors}

    first = [o for o in obs if _utc(o.timestamp) < mid]
    second = [o for o in obs if _utc(o.timestamp) >= mid]
    afirst = [a for a in anoms if _utc(a.timestamp) < mid]
    asecond = [a for a in anoms if _utc(a.timestamp) >= mid]
    cadence = _median_cadence(obs)

    out = []
    for s in SENSORS:
        f = FIELD[s]
        sa1 = [a for a in afirst if s in implicated_sensors(a)]
        sa2 = [a for a in asecond if s in implicated_sensors(a)]
        r1 = len(sa1) / len(first) if first else 0.0
        r2 = len(sa2) / len(second) if second else 0.0
        total = len(sa1) + len(sa2)

        freq = _clamp01((r2 - r1) * 10.0) if total >= 3 else 0.0

        d1 = _slope_per_day([(_utc(o.timestamp), getattr(o, f)) for o in first if getattr(o, f) is not None])
        d2 = _slope_per_day([(_utc(o.timestamp), getattr(o, f)) for o in second if getattr(o, f) is not None])
        if d1 is None or d2 is None:
            drift = 0.0
            drift_info = {"before": None, "recent": None}
        else:
            drift = _clamp01((abs(d2) - abs(d1)) / DRIFT_LIMIT_PER_DAY[s])
            drift_info = {"before": round(d1, 3), "recent": round(d2, 3)}

        types = Counter((a.anomaly_type or a.root_cause or "UNKNOWN") for a in sa1 + sa2)
        top, topn = (types.most_common(1)[0] if types else ("-", 0))
        repeated = _clamp01((topn - 1) / 5.0)

        decline_pts = max(0.0, then_by[s].score - now_by[s].score)
        decline = _clamp01(decline_pts / 25.0)

        m1, m2 = _miss_rate(first, cadence), _miss_rate(second, cadence)
        missing = _clamp01((m2 - m1) * 3.0)

        comm_n = sum(1 for a in sa1 + sa2
                     if (a.anomaly_type or "") == "COMMUNICATION_FAILURE"
                     or (a.root_cause or "") == "COMMUNICATION_FAILURE")
        gaps = sorted(
            (b - a).total_seconds() / 60.0
            for a, b in zip(sorted(_utc(o.timestamp) for o in second),
                            sorted(_utc(o.timestamp) for o in second)[1:])
            if (b - a).total_seconds() > 0
        )
        burst = _clamp01((statistics.pstdev(gaps) / statistics.mean(gaps) - 1.0) / 2.0) if len(gaps) >= 5 else 0.0
        comm = max(_clamp01(comm_n / 4.0), burst)

        signals = {
            "frequency_up": round(freq, 3),
            "drift_up": round(drift, 3),
            "repeated": round(repeated, 3),
            "decline": round(decline, 3),
            "missing_up": round(missing, 3),
            "comm": round(comm, 3),
        }
        risk = round(100.0 * sum(signals[k] * SIGNAL_WEIGHTS[k] for k in signals), 2)
        level = "HIGH" if risk >= 60 else ("MEDIUM" if risk >= 35 else "LOW")
        health_now = now_by[s].score
        if level == "HIGH" and (health_now < 40 or comm_n > 0 and m2 > 0):
            priority = "URGENT"
        elif level == "HIGH":
            priority = "HIGH"
        elif level == "MEDIUM":
            priority = "MEDIUM"
        else:
            priority = "LOW"

        bits = []
        if freq > 0:
            bits.append(f"anomaly rate rose {r1:.3f} -> {r2:.3f} per reading ({len(sa1)} before vs {len(sa2)} recent)")
        if drift > 0:
            bits.append(f"daily-mean drift steepened {drift_info['before']} -> {drift_info['recent']} {UNIT[s]}/day")
        if repeated > 0:
            bits.append(f"'{top}' recurred {topn}x in the window")
        if decline > 0:
            bits.append(f"health declined {then_by[s].score:.0f} -> {health_now:.0f}")
        if missing > 0:
            bits.append(f"missing-data rate rose {m1:.2f} -> {m2:.2f}")
        if comm > 0:
            bits.append(f"communication instability: {comm_n} comm-failure flags, gap burstiness present"
                        if burst > 0 else f"communication instability: {comm_n} comm-failure flags")
        reason = "; ".join(bits) if bits else "no measured degradation trend; readings nominal"

        actions = list(BASE_ACTIONS[s])
        for sig in ("frequency_up", "drift_up", "repeated", "decline", "missing_up", "comm"):
            if signals[sig] >= 0.4:
                extra = SIGNAL_ACTIONS[sig]
                if extra not in actions:
                    actions.append(extra)

        out.append(SensorMaintenance(
            station_id=station_id, sensor_type=s, health=health_now,
            health_status=now_by[s].status, maintenance_risk=risk, risk_level=level,
            maintenance_priority=priority, reason=reason,
            recommended_action=actions, signals={**signals, "drift_detail": drift_info,
                                                 "rates": {"before": round(r1, 4), "recent": round(r2, 4)}}))
    return out


async def sync_recommendations(
    session: AsyncSession, station_id: str, window_days: float = 30.0, end: datetime | None = None
) -> list[SensorMaintenance]:
    """Upsert one OPEN work order per at-risk sensor. Idempotent: no duplicates."""
    intel = await analyze_station(session, station_id, window_days, end)
    for item in intel:
        if item.maintenance_priority == "LOW":
            continue
        tag = f"[{item.sensor_type}]"
        existing = (
            await session.execute(
                select(MaintenanceRecommendation).where(
                    MaintenanceRecommendation.station_id == station_id,
                    MaintenanceRecommendation.status == "OPEN",
                )
            )
        ).scalars().all()
        mine = next((r for r in existing if (r.recommendation or "").startswith(tag)), None)
        text = f"{tag} risk {item.risk_level} ({item.maintenance_risk:.0f}/100), health {item.health:.0f}: " + "; ".join(item.recommended_action[:3])
        if mine is None:
            session.add(MaintenanceRecommendation(
                station_id=station_id, priority=item.maintenance_priority,
                recommendation=text[:500], reason=item.reason[:500]))
        else:
            mine.priority = item.maintenance_priority
            mine.recommendation = text[:500]
            mine.reason = item.reason[:500]
    await session.flush()
    return intel
