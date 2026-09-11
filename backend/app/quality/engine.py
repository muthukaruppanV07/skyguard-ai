"""Data quality engine: 5 dimensions + 8 issue types, all counted from data.

Dimensions (0-100, trailing window):
- completeness: actual vs expected observations from median cadence.
- validity: share of readings inside physical plausibility ranges.
- consistency: 100 minus penalties for frozen runs + spike/drift/MV anomaly shares.
- timeliness: freshness of the latest reading vs cadence (100 if within 2x,
  decaying to 0 at 24x; no receive-timestamps exist, so staleness is the
  honest proxy and is labeled as such).
- overall: mean of the four.

Issue types detected: missing_values, invalid_values, duplicate_records,
frozen_sensor, comm_gaps, spikes, drift, multivariate.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.health.engine import _utc, implicated_sensors
from backend.app.models.anomaly import Anomaly
from backend.app.models.observation import Observation
from backend.app.models.station import Station

FIELD = {"TEMPERATURE": "temperature", "PRESSURE": "pressure", "HUMIDITY": "humidity"}
RANGES = {"TEMPERATURE": (settings.TEMP_MIN, settings.TEMP_MAX),
          "PRESSURE": (settings.PRESSURE_MIN, settings.PRESSURE_MAX),
          "HUMIDITY": (settings.HUMIDITY_MIN, settings.HUMIDITY_MAX)}
FROZEN_RUN = 6

SPIKE_TYPES = {"TEMPERATURE_SPIKE", "TEMPERATURE_DROP", "PRESSURE_ANOMALY", "HUMIDITY_ANOMALY"}
ISSUE_TYPES = ("missing_values", "invalid_values", "duplicate_records", "frozen_sensor",
               "comm_gaps", "spikes", "drift", "multivariate")


@dataclass
class StationQuality:
    station_id: str
    completeness: float
    validity: float
    consistency: float
    timeliness: float
    overall: float
    counts: dict = field(default_factory=dict)


def _median_cadence_min(ts: list[datetime]) -> float:
    if len(ts) < 3:
        return 0.0
    gaps = [(b - a).total_seconds() / 60.0 for a, b in zip(ts, ts[1:]) if (b - a).total_seconds() > 0]
    return statistics.median(gaps) if gaps else 0.0


def _runs(values: list) -> list[tuple]:
    """Max identical-value run per sensor: [(sensor, length, end_index)]."""
    out = []
    for s, f in FIELD.items():
        best = cur = 0
        prev = object()
        end = 0
        for i, o in enumerate(values):
            v = getattr(o, f)
            cur = cur + 1 if v == prev else 1
            prev = v
            if cur > best:
                best, end = cur, i
        out.append((s, best, end))
    return out


async def station_quality(session: AsyncSession, station_id: str,
                          hours: int = 168, end: datetime | None = None) -> tuple[StationQuality, list[dict]]:
    end = _utc(end or datetime.now(timezone.utc))
    start = end - timedelta(hours=hours)
    obs = (await session.execute(
        select(Observation).where(Observation.station_id == station_id,
                                  Observation.timestamp >= start.replace(tzinfo=None),
                                  Observation.timestamp <= end.replace(tzinfo=None))
        .order_by(Observation.timestamp))).scalars().all()
    obs = list(obs)
    anoms = (await session.execute(
        select(Anomaly).where(Anomaly.station_id == station_id,
                              Anomaly.timestamp >= start.replace(tzinfo=None),
                              Anomaly.timestamp <= end.replace(tzinfo=None))
        .order_by(Anomaly.timestamp))).scalars().all()
    anoms = list(anoms)
    issues: list[dict] = []

    # completeness + missing gaps
    ts = sorted(_utc(o.timestamp) for o in obs)
    cadence = _median_cadence_min(ts)
    if len(obs) >= 2 and cadence > 0:
        span_min = (ts[-1] - ts[0]).total_seconds() / 60.0
        expected = max(1.0, span_min / cadence + 1)
        completeness = round(max(0.0, min(100.0, len(obs) / expected * 100.0)), 1)
        for a, b in zip(ts, ts[1:]):
            if (b - a).total_seconds() / 60.0 > 3 * cadence:
                issues.append({"station_id": station_id, "parameter": "all",
                               "timestamp": a.isoformat(), "issue_type": "missing_values",
                               "detail": f"gap {(b - a).total_seconds() / 3600:.1f}h (cadence {cadence:.0f}min)",
                               "severity": "HIGH"})
    else:
        completeness = 100.0 if obs else 0.0

    # validity
    bad = 0
    total_vals = 0
    for o in obs:
        for s, f in FIELD.items():
            v = getattr(o, f)
            if v is None:
                continue
            total_vals += 1
            lo, hi = RANGES[s]
            if not lo <= v <= hi:
                bad += 1
                issues.append({"station_id": station_id, "parameter": s,
                               "timestamp": _utc(o.timestamp).isoformat(), "issue_type": "invalid_values",
                               "detail": f"{s}={v} outside [{lo},{hi}]", "severity": "CRITICAL"})
    validity = round(max(0.0, 100.0 - (bad / total_vals * 100.0)) if total_vals else 100.0, 1)

    # duplicates (same station+timestamp more than once)
    dup = (await session.execute(
        select(Observation.timestamp, func.count(Observation.id))
        .where(Observation.station_id == station_id,
               Observation.timestamp >= start.replace(tzinfo=None),
               Observation.timestamp <= end.replace(tzinfo=None))
        .group_by(Observation.timestamp).having(func.count(Observation.id) > 1))).all()
    for tst, n in dup:
        issues.append({"station_id": station_id, "parameter": "all",
                       "timestamp": _utc(tst).isoformat(), "issue_type": "duplicate_records",
                       "detail": f"{n} records share timestamp {tst}", "severity": "MEDIUM"})

    # consistency: frozen runs + anomaly shares
    frozen_hit = 0
    for s, length, end_i in _runs(obs):
        if length >= FROZEN_RUN:
            frozen_hit += 1
            issues.append({"station_id": station_id, "parameter": s,
                           "timestamp": _utc(obs[end_i].timestamp).isoformat(),
                           "issue_type": "frozen_sensor",
                           "detail": f"{s} identical {length}x in a row", "severity": "HIGH"})
    spike_n = drift_n = mv_n = comm_n = 0
    for a in anoms:
        at = (a.anomaly_type or "") or (a.root_cause or "")
        sensors = sorted(implicated_sensors(a))
        if at in SPIKE_TYPES:
            spike_n += 1
            itype = "spikes"
        elif at == "SENSOR_DRIFT":
            drift_n += 1
            itype = "drift"
        elif at == "MULTIVARIATE_INCONSISTENCY":
            mv_n += 1
            itype = "multivariate"
        elif at == "COMMUNICATION_FAILURE":
            comm_n += 1
            itype = "comm_gaps"
        else:
            continue
        issues.append({"station_id": station_id, "parameter": ",".join(sensors),
                       "timestamp": _utc(a.timestamp).isoformat(), "issue_type": itype,
                       "detail": f"{at} score={a.score:.0f}", "severity": a.severity or "LOW"})
    n = max(1, len(obs))
    consistency = round(max(0.0, 100.0 - min(40.0, frozen_hit * 10.0)
                            - min(30.0, spike_n / n * 300.0)
                            - min(15.0, drift_n * 3.0) - min(15.0, mv_n * 5.0)), 1)

    # timeliness: freshness of latest reading vs cadence
    if ts and cadence > 0:
        age_min = (end - ts[-1]).total_seconds() / 60.0
        timeliness = round(max(0.0, min(100.0, 100.0 - max(0.0, age_min / cadence - 2) * 10.0)), 1)
    else:
        timeliness = 0.0 if not ts else 100.0

    overall = round((completeness + validity + consistency + timeliness) / 4.0, 1)
    counts = Counter(i["issue_type"] for i in issues)
    sq = StationQuality(station_id, completeness, validity, consistency, timeliness, overall, dict(counts))
    # newest first
    issues.sort(key=lambda i: i["timestamp"], reverse=True)
    return sq, issues


async def fleet_quality(session: AsyncSession, hours: int = 168,
                        end: datetime | None = None) -> dict:
    stations = (await session.execute(select(Station).where(Station.station_id != "SYSTEM").order_by(Station.station_id))).scalars().all()
    per, all_issues = [], []
    for st in stations:
        sq, issues = await station_quality(session, st.station_id, hours, end)
        per.append(sq)
        all_issues.extend(issues)
    dims = ("completeness", "validity", "consistency", "timeliness", "overall")
    fleet = {d: round(sum(getattr(s, d) for s in per) / len(per), 1) if per else 0.0 for d in dims}
    return {"fleet": fleet,
            "stations": [{"station_id": s.station_id, "completeness": s.completeness,
                          "validity": s.validity, "consistency": s.consistency,
                          "timeliness": s.timeliness, "overall": s.overall, "counts": s.counts} for s in per],
            "issue_counts": dict(Counter(i["issue_type"] for i in all_issues)),
            "total_issues": len(all_issues)}
