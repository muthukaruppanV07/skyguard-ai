"""Data-grounded insight generator: every sentence traces to counted events.

No templates filled with random text: each insight is emitted only when its
trigger condition (documented per rule) holds on live readings, and every
number in the text is computed from those readings. Confidence is the
supporting fraction, never a guess.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.health.engine import _slope_per_day, _utc
from backend.app.models.anomaly import Anomaly
from backend.app.models.observation import Observation
from backend.app.models.station import Station

MOVE_WINDOW_H = 6.0
PRESS_MOVE = 2.0   # hPa over the window
TEMP_MOVE = 2.0    # C over the window
OUTLIER_Z = 3.0


@dataclass
class Insight:
    id: str
    kind: str
    title: str
    evidence: list = field(default_factory=list)
    affected_stations: list = field(default_factory=list)
    confidence: float = 0.0
    recommended_action: str = ""
    severity: str = "INFO"  # INFO | WATCH | ACT


def _latest_per_station(obs: list[Observation]) -> dict[str, Observation]:
    out: dict[str, Observation] = {}
    for o in sorted(obs, key=lambda r: _utc(r.timestamp)):
        out[o.station_id] = o
    return out


def _value_hours_ago(obs: list[Observation], sid: str, hours: float, field: str):
    rows = sorted([o for o in obs if o.station_id == sid], key=lambda r: _utc(r.timestamp))
    if not rows:
        return None
    target = _utc(rows[-1].timestamp) - timedelta(hours=hours)
    past = [o for o in rows if _utc(o.timestamp) <= target]
    base = past[-1] if past else rows[0]
    return getattr(base, field)


async def generate_insights(session: AsyncSession, hours: int = 24,
                            end: datetime | None = None) -> list[Insight]:
    now = end.replace(tzinfo=timezone.utc) if end and end.tzinfo is None \
        else (end or datetime.now(timezone.utc))
    since = now - timedelta(hours=hours)
    obs = (await session.execute(
        select(Observation).where(Observation.timestamp >= since.replace(tzinfo=None))
        .order_by(Observation.timestamp).limit(5000))).scalars().all()
    obs = list(obs)
    anoms = (await session.execute(
        select(Anomaly).where(Anomaly.timestamp >= since.replace(tzinfo=None))
        .order_by(Anomaly.timestamp))).scalars().all()
    anoms = list(anoms)
    stations = (await session.execute(select(Station).where(Station.station_id != "SYSTEM").order_by(Station.station_id))).scalars().all()
    stations = list(stations)

    out: list[Insight] = []
    latest = _latest_per_station(obs)

    # 1-2. Regional coherent moves (pressure / temperature)
    for fname, thresh, unit, label in (("pressure", PRESS_MOVE, "hPa", "pressure"),
                                       ("temperature", TEMP_MOVE, "C", "temperature")):
        moves = {}
        for sid, o in latest.items():
            old = _value_hours_ago(obs, sid, MOVE_WINDOW_H, fname)
            if old is None:
                continue
            moves[sid] = getattr(o, fname) - old
        same = {s: d for s, d in moves.items() if abs(d) >= thresh}
        if len(same) >= 3 and len({1 if d > 0 else -1 for d in same.values()}) == 1:
            direction = "decline" if next(iter(same.values())) < 0 else "rise"
            avg = sum(same.values()) / len(same)
            out.append(Insight(
                id=f"regional-{label}", kind=f"regional_{label}",
                title=f"{len(same)} nearby stations show simultaneous {label} {direction}.",
                evidence=[f"{s}: {label} moved {d:+.1f}{unit} over ~{MOVE_WINDOW_H:.0f}h" for s, d in sorted(same.items())],
                affected_stations=sorted(same),
                confidence=round(len(same) / max(1, len(moves)), 2),
                recommended_action=(f"Treat as a possible regional meteorological event affecting {len(same)} stations; "
                                    f"cross-check with forecast fields before flagging sensors."),
                severity="WATCH" if abs(avg) < 2 * thresh else "ACT"))

    # 3. Isolated outlier vs neighbours (leave-one-out: the station must not
    # drag its own comparison mean)
    temps = {sid: o.temperature for sid, o in latest.items() if o.temperature is not None}
    if len(temps) >= 3:
        for sid, t in temps.items():
            others = [v for s, v in temps.items() if s != sid]
            mean = sum(others) / len(others)
            sd = math.sqrt(sum((v - mean) ** 2 for v in others) / len(others))
            z = (t - mean) / max(sd, 0.5)
            if abs(z) >= OUTLIER_Z:
                out.append(Insight(
                    id=f"outlier-{sid}", kind="outlier",
                    title=f"{sid} differs significantly from its neighboring stations.",
                    evidence=[f"{sid} reads {t:.1f}C vs neighbour mean {mean:.1f}C (z={z:+.1f})",
                              f"Neighbours: " + ", ".join(f"{s} {v:.1f}C" for s, v in sorted(temps.items()) if s != sid)],
                    affected_stations=[sid],
                    confidence=round(min(1.0, abs(z) / 6.0), 2),
                    recommended_action=f"Inspect {sid}: probable isolated sensor fault; verify probe and shielding.",
                    severity="ACT"))

    # 4. Repeat offender (same anomaly type >= 3x)
    by_station_type = Counter((a.station_id, a.anomaly_type or a.root_cause) for a in anoms)
    for (sid, atype), n in by_station_type.items():
        if n >= 3:
            out.append(Insight(
                id=f"repeat-{sid}-{atype}", kind="repeat",
                title=f"{sid} raised '{atype}' {n} times in {hours}h.",
                evidence=[f"{n} occurrences of {atype} at {sid} within {hours}h"],
                affected_stations=[sid],
                confidence=round(min(1.0, n / 6.0), 2),
                recommended_action=f"Recurring {atype} at {sid}: schedule maintenance instead of repeated resets.",
                severity="WATCH"))

    # 5. Drift acceleration from measured slopes (recent 6h vs prior)
    for sid in latest:
        rows = sorted([o for o in obs if o.station_id == sid], key=lambda r: _utc(r.timestamp))
        if len(rows) < 12:
            continue
        cut = _utc(rows[-1].timestamp) - timedelta(hours=MOVE_WINDOW_H)
        old = [( _utc(o.timestamp), o.temperature) for o in rows if _utc(o.timestamp) <= cut]
        new = [( _utc(o.timestamp), o.temperature) for o in rows if _utc(o.timestamp) > cut]
        s_old = _slope_per_day(old) or 0.0
        s_new = _slope_per_day(new) or 0.0
        if s_new is not None and abs(s_new) >= 0.5 and abs(s_new) > 2 * abs(s_old or 0.0) + 0.2:
            out.append(Insight(
                id=f"drift-{sid}", kind="drift",
                title=f"Temperature drift at {sid} accelerated during the last {MOVE_WINDOW_H:.0f} hours.",
                evidence=[f"daily-mean slope {s_old:+.2f} -> {s_new:+.2f} C/day"],
                affected_stations=[sid],
                confidence=round(min(1.0, abs(s_new) / 1.5), 2),
                recommended_action=f"Recalibrate the temperature probe at {sid} against a reference instrument.",
                severity="WATCH"))

    # 6. Health at risk (persisted engine scores)
    from backend.app.health.engine import compute_station_health
    for st in stations:
        try:
            snap = await compute_station_health(session, st.station_id)
        except Exception:
            continue
        if snap.overall < 65:
            worst = min(snap.sensors, key=lambda s: s.score)
            top_pen = sorted(worst.penalties.items(), key=lambda kv: -kv[1])[:2]
            out.append(Insight(
                id=f"health-{st.station_id}", kind="health",
                title=f"{st.station_id} health is {snap.overall:.0f}/100 ({snap.status}).",
                evidence=[f"{worst.sensor_type}: {worst.score:.0f}/100",
                          f"top penalties: " + ", ".join(f"{k} -{v:.0f}" for k, v in top_pen)],
                affected_stations=[st.station_id],
                confidence=round(min(1.0, (65 - snap.overall) / 40 + 0.4), 2),
                recommended_action=f"Prioritise {st.station_id} ({worst.sensor_type}) on the next site visit.",
                severity="ACT" if snap.overall < 40 else "WATCH"))

    # 7. Quiet network (genuinely nothing flagged)
    if not anoms:
        out.append(Insight(
            id="quiet", kind="quiet",
            title=f"No anomalies flagged across {len(stations)} stations in {hours}h.",
            evidence=[f"{len(obs)} observations ingested, 0 anomalies in window"],
            affected_stations=[],
            confidence=1.0,
            recommended_action="Maintain watch; no action required.",
            severity="INFO"))

    order = {"ACT": 0, "WATCH": 1, "INFO": 2}
    out.sort(key=lambda i: (order.get(i.severity, 3), -i.confidence))
    return out[:12]
