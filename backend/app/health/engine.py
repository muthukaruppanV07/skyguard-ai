"""Sensor health engine: 0-100 scores derived from actual station behaviour.

No randomness, no blind +/- deltas: every point subtracted traces to a
counted event (anomaly rows, identical-value runs, expected-vs-actual
observation counts, measured drift slopes). Same history in -> same
score out, always.

Per-sensor penalties (each capped, subtracted from 100):
  anomaly_frequency   share of observations flagged (x200, cap 30)
  anomaly_severity    mean severity weight (x20, cap 20)
  sensor_drift        trailing slope vs per-day limit (x7.5, cap 15)
  frozen_readings     longest identical-value run (cap 15)
  missing_observations expected-vs-actual count from median cadence (cap 10)
  communication_failures comm-failure anomaly count (x2, cap 10)
  recent_reliability  anomaly rate over the recent slice (x60, cap 15)
  repeated_abnormal   recurrence of the dominant anomaly type (cap 10)

Statuses: EXCELLENT (>=85) | GOOD (>=65) | WARNING (>=40) | CRITICAL (<40).
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.anomaly import Anomaly
from backend.app.models.observation import Observation

SENSORS = ("TEMPERATURE", "PRESSURE", "HUMIDITY")
FIELD = {"TEMPERATURE": "temperature", "PRESSURE": "pressure", "HUMIDITY": "humidity"}

SEVERITY_WEIGHT = {"CRITICAL": 1.0, "HIGH": 0.7, "SUSPICIOUS": 0.4, "LOW": 0.2, "NORMAL": 0.0}
DRIFT_LIMIT_PER_DAY = {"TEMPERATURE": 0.5, "PRESSURE": 1.0, "HUMIDITY": 2.0}


def status_for(score: float) -> str:
    if score >= 85:
        return "EXCELLENT"
    if score >= 65:
        return "GOOD"
    if score >= 40:
        return "WARNING"
    return "CRITICAL"


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@dataclass
class SensorScore:
    sensor_type: str
    score: float
    status: str
    anomaly_count: int
    penalties: dict = field(default_factory=dict)


@dataclass
class StationHealth:
    station_id: str
    overall: float
    status: str
    sensors: list = field(default_factory=list)
    as_of: datetime | None = None


def implicated_sensors(anomaly: Anomaly) -> set[str]:
    """Which sensors an anomaly row implicates (name match, else all)."""
    text = f"{anomaly.anomaly_type or ''} {anomaly.root_cause or ''} {anomaly.message or ''}".upper()
    hit = {s for s in SENSORS if s in text}
    return hit or set(SENSORS)


def _slope_per_day(points: list[tuple[datetime, float]]) -> float | None:
    """Slope of DAILY MEANS (diurnal cycles removed), needs >= 5 days.

    Raw slopes over short windows mistake the normal day/night cycle for
    drift, so short histories abstain (None) instead of false-alarming.
    """
    by_day: dict[str, list[float]] = {}
    for t, v in points:
        by_day[t.date().isoformat()] = by_day.get(t.date().isoformat(), []) + [v]
    if len(by_day) < 5:
        return None
    days = sorted(by_day)
    means = [sum(by_day[d]) / len(by_day[d]) for d in days]
    n = len(days)
    xs = list(range(n))
    sx, sy = sum(xs), sum(means)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * m for x, m in zip(xs, means))
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


def _max_identical_run(values: list[float]) -> int:
    best = cur = 0
    prev = object()
    for v in values:
        cur = cur + 1 if v == prev else 1
        prev = v
        best = max(best, cur)
    return best


async def _window_data(session: AsyncSession, station_id: str, start: datetime, end: datetime):
    obs = (
        await session.execute(
            select(Observation)
            .where(Observation.station_id == station_id,
                   Observation.timestamp >= start, Observation.timestamp <= end)
            .order_by(Observation.timestamp)
        )
    ).scalars().all()
    anoms = (
        await session.execute(
            select(Anomaly)
            .where(Anomaly.station_id == station_id,
                   Anomaly.timestamp >= start, Anomaly.timestamp <= end)
            .order_by(Anomaly.timestamp)
        )
    ).scalars().all()
    return list(obs), list(anoms)


def _score_sensors(obs, anoms, window_days: float) -> list[SensorScore]:
    n_obs = len(obs)
    by_sensor_anoms: dict[str, list] = {s: [] for s in SENSORS}
    for a in anoms:
        for s in implicated_sensors(a):
            by_sensor_anoms[s].append(a)

    # Station-wide cadence -> expected observation count
    miss_rate = 0.0
    if len(obs) >= 3:
        ts = sorted(_utc(o.timestamp) for o in obs)
        gaps = [(b - a).total_seconds() / 60.0 for a, b in zip(ts, ts[1:]) if (b - a).total_seconds() > 0]
        if gaps:
            median_min = statistics.median(gaps) or 60.0
            span_min = (ts[-1] - ts[0]).total_seconds() / 60.0
            expected = max(1.0, span_min / median_min + 1)
            miss_rate = max(0.0, 1.0 - len(obs) / expected)
    comm_count = sum(1 for a in anoms if (a.anomaly_type or "") == "COMMUNICATION_FAILURE"
                     or (a.root_cause or "") == "COMMUNICATION_FAILURE")

    # Recent slice: last 3 days (or whole window if shorter)
    recent_cut_days = min(3.0, window_days)
    recent_n = 0
    recent_a = 0
    if obs:
        latest = max(_utc(o.timestamp) for o in obs)
        recent_obs = [o for o in obs if (latest - _utc(o.timestamp)).total_seconds() <= recent_cut_days * 86400]
        recent_n = len(recent_obs)
        if recent_obs:
            t0 = min(_utc(o.timestamp) for o in recent_obs)
            recent_a = sum(1 for a in anoms if _utc(a.timestamp) >= t0)
    recent_rate = (recent_a / recent_n) if recent_n else 0.0

    out = []
    for s in SENSORS:
        f = FIELD[s]
        vals = [( _utc(o.timestamp), getattr(o, f)) for o in obs]
        vals = [(t, v) for t, v in vals if v is not None]
        sa = by_sensor_anoms[s]
        pen: dict[str, float] = {}

        pen["anomaly_frequency"] = round(min(30.0, (len(sa) / n_obs * 200.0) if n_obs else 0.0), 2)
        sev = [SEVERITY_WEIGHT.get((a.severity or "NORMAL").upper(), 0.4) for a in sa]
        pen["anomaly_severity"] = round(min(20.0, (sum(sev) / len(sev) * 20.0) if sev else 0.0), 2)

        slope = _slope_per_day(vals)
        ratio = abs(slope) / DRIFT_LIMIT_PER_DAY[s] if slope is not None else 0.0
        pen["sensor_drift"] = round(min(15.0, ratio * 7.5), 2)

        streak = _max_identical_run([v for _, v in vals])
        pen["frozen_readings"] = round(min(15.0, max(0.0, streak - 2) * 1.5), 2)

        pen["missing_observations"] = round(min(10.0, miss_rate * 40.0), 2)
        pen["communication_failures"] = round(min(10.0, comm_count * 2.0), 2)
        pen["recent_reliability"] = round(min(15.0, recent_rate * 60.0), 2)

        types = Counter((a.anomaly_type or a.root_cause or "UNKNOWN") for a in sa)
        top = max(types.values()) if types else 0
        pen["repeated_abnormal"] = round(min(10.0, max(0, top - 1) * 2.0), 2)

        score = round(max(0.0, 100.0 - sum(pen.values())), 2)
        out.append(SensorScore(s, score, status_for(score), len(sa), pen))
    return out


async def compute_station_health(
    session: AsyncSession,
    station_id: str,
    window_days: float = 30.0,
    end: datetime | None = None,
) -> StationHealth:
    """Full health snapshot over the trailing window ending at `end`."""
    end = _utc(end or datetime.now(timezone.utc))
    start = end - timedelta(days=window_days)
    obs, anoms = await _window_data(session, station_id, start.replace(tzinfo=None), end.replace(tzinfo=None))
    sensors = _score_sensors(obs, anoms, window_days)
    overall = round(sum(s.score for s in sensors) / len(sensors), 2)
    return StationHealth(station_id, overall, status_for(overall), sensors, end)


async def health_trend(
    session: AsyncSession,
    station_id: str,
    days: int = 14,
    window_days: float = 30.0,
    end: datetime | None = None,
) -> list[dict]:
    """Daily trailing-window overall scores. Every point recomputed from events."""
    now = _utc(end or datetime.now(timezone.utc))
    trend = []
    for back in range(days - 1, -1, -1):
        day_end = now - timedelta(days=back)
        snap = await compute_station_health(session, station_id, window_days, day_end)
        trend.append({"date": day_end.date().isoformat(), "score": snap.overall, "status": snap.status})
    return trend


async def recompute_and_store(session: AsyncSession, station_id: str, window_days: float = 30.0) -> StationHealth:
    """Recompute from history and persist per-sensor rows. Called on ingest."""
    from backend.app.models.sensor_health import SensorHealth

    snap = await compute_station_health(session, station_id, window_days)
    for s in snap.sensors:
        row = (
            await session.execute(
                select(SensorHealth).where(
                    SensorHealth.station_id == station_id, SensorHealth.sensor_type == s.sensor_type
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = SensorHealth(station_id=station_id, sensor_type=s.sensor_type)
            session.add(row)
        row.score = s.score
        row.status = s.status
        row.anomaly_count = s.anomaly_count
        row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return snap
