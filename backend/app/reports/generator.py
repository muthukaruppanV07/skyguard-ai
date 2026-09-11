"""Report builders: five operational reports, all computed from live tables.

Each builder returns {"title", "summary", "sections", "csv"} where sections
are render blocks ({kind: kpi|table|list, ...}) and csv is {columns, rows}
for export. Nothing is narrated without a backing count.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.health.engine import _utc, compute_station_health, health_trend
from backend.app.health.maintenance import analyze_station
from backend.app.models.anomaly import Anomaly
from backend.app.models.maintenance import MaintenanceRecommendation
from backend.app.models.observation import Observation
from backend.app.models.station import Station
from backend.app.quality.engine import fleet_quality

REPORT_TYPES = {
    "daily_quality": "Daily AWS Quality Report",
    "weekly_anomaly": "Weekly Anomaly Report",
    "station_health": "Station Health Report",
    "maintenance": "Maintenance Report",
    "regional_quality": "Regional Data Quality Report",
}


def zone_of(lat: float) -> str:
    if lat >= 25:
        return "NORTH"
    if lat >= 20:
        return "CENTRAL"
    return "SOUTH"


async def _stations(session: AsyncSession, station_id: str | None) -> list[Station]:
    if station_id:
        st = await session.get(Station, station_id)
        if st is None or st.station_id == "SYSTEM":
            raise ValueError(f"Unknown station_id: {station_id}")
        return [st]
    rows = (await session.execute(
        select(Station).where(Station.station_id != "SYSTEM").order_by(Station.station_id))).scalars().all()
    return list(rows)


async def _anoms(session: AsyncSession, sids: list[str], start, end) -> list[Anomaly]:
    rows = (await session.execute(
        select(Anomaly).where(Anomaly.station_id.in_(sids),
                              Anomaly.timestamp >= start.replace(tzinfo=None),
                              Anomaly.timestamp <= end.replace(tzinfo=None))
        .order_by(desc(Anomaly.timestamp)))).scalars().all()
    return list(rows)


async def _obs_count(session: AsyncSession, sids: list[str], start, end) -> int:
    return (await session.execute(
        select(func.count()).select_from(Observation).where(
            Observation.station_id.in_(sids),
            Observation.timestamp >= start.replace(tzinfo=None),
            Observation.timestamp <= end.replace(tzinfo=None)))).scalar_one()


def _sev_counts(anoms: list[Anomaly]) -> dict:
    return dict(Counter((a.severity or "UNKNOWN") for a in anoms))


def _kpi(label: str, value) -> dict:
    return {"kind": "kpi", "label": label, "value": value}


def _table(columns: list[str], rows: list[list]) -> dict:
    return {"kind": "table", "columns": columns, "rows": rows}


async def daily_quality(session: AsyncSession, station_id: str | None = None,
                        days: int = 1, end: datetime | None = None) -> dict:
    end = _utc(end or datetime.now(timezone.utc))
    start = end - timedelta(days=days)
    stations = await _stations(session, station_id)
    sids = [s.station_id for s in stations]
    anoms = await _anoms(session, sids, start, end)
    n_obs = await _obs_count(session, sids, start, end)
    dq = await fleet_quality(session, hours=24 * days, end=end)
    per = {s["station_id"]: s for s in dq["stations"]}
    per_obs: dict[str, int] = {}
    for s in stations:
        per_obs[s.station_id] = await _obs_count(session, [s.station_id], start, end)
    fleet_overall = round(sum(x["overall"] for x in dq["stations"]) / len(dq["stations"]), 1) if dq["stations"] else 0.0
    sections = [
        _kpi("observations", n_obs),
        _kpi("anomalies", len(anoms)),
        _kpi("overall_quality", fleet_overall),
        _table(["station", "observations", "anomalies", "overall"],
               [[s.station_id, per_obs[s.station_id],
                 sum(1 for a in anoms if a.station_id == s.station_id),
                 per.get(s.station_id, {}).get("overall", "—")] for s in stations]),
        _table(["severity", "count"], sorted(_sev_counts(anoms).items())),
    ]
    csv_rows = [{"station_id": s.station_id, "overall": per.get(s.station_id, {}).get("overall"),
                 "anomalies": sum(1 for a in anoms if a.station_id == s.station_id)} for s in stations]
    return {"title": REPORT_TYPES["daily_quality"], "window_days": days,
            "summary": f"{n_obs} observations, {len(anoms)} anomalies across {len(stations)} stations.",
            "sections": sections,
            "csv": {"columns": ["station_id", "overall", "anomalies"], "rows": csv_rows}}


async def weekly_anomaly(session: AsyncSession, station_id: str | None = None,
                         days: int = 7, end: datetime | None = None) -> dict:
    end = _utc(end or datetime.now(timezone.utc))
    start = end - timedelta(days=days)
    stations = await _stations(session, station_id)
    sids = [s.station_id for s in stations]
    anoms = await _anoms(session, sids, start, end)
    by_type = Counter((a.anomaly_type or a.root_cause or "UNKNOWN") for a in anoms)
    conf = [a.confidence for a in anoms if a.confidence is not None]
    sections = [
        _kpi("anomalies", len(anoms)),
        _kpi("mean_confidence", round(sum(conf) / len(conf), 3) if conf else 0.0),
        _kpi("stations_affected", len({a.station_id for a in anoms})),
        _table(["root_cause", "count"], sorted(by_type.items(), key=lambda kv: -kv[1])),
        _table(["severity", "count"], sorted(_sev_counts(anoms).items())),
        _table(["id", "station", "timestamp", "root_cause", "score", "severity", "confidence", "resolved"],
               [[a.id, a.station_id, _utc(a.timestamp).isoformat(), a.anomaly_type or a.root_cause,
                 a.score, a.severity, a.confidence, bool(a.resolved)] for a in anoms[:200]]),
    ]
    return {"title": REPORT_TYPES["weekly_anomaly"], "window_days": days,
            "summary": f"{len(anoms)} anomalies in {days}d across {len({a.station_id for a in anoms})} stations.",
            "sections": sections,
            "csv": {"columns": ["id", "station", "timestamp", "root_cause", "score", "severity", "confidence"],
                    "rows": [{"id": a.id, "station": a.station_id,
                              "timestamp": _utc(a.timestamp).isoformat(),
                              "root_cause": a.anomaly_type or a.root_cause, "score": a.score,
                              "severity": a.severity, "confidence": a.confidence} for a in anoms[:500]]}}


async def station_health_report(session: AsyncSession, station_id: str | None = None,
                                days: int = 14, end: datetime | None = None) -> dict:
    end = _utc(end or datetime.now(timezone.utc))
    stations = await _stations(session, station_id)
    rows, csv_rows, trends = [], [], {}
    for st in stations:
        snap = await compute_station_health(session, st.station_id, 30.0, end)
        rows.append([st.station_id, snap.overall, snap.status,
                     "; ".join(f"{s.sensor_type} {s.score:.0f} ({s.status})" for s in snap.sensors)])
        for s in snap.sensors:
            csv_rows.append({"station_id": st.station_id, "sensor": s.sensor_type,
                             "score": s.score, "status": s.status,
                             "anomalies": s.anomaly_count})
        trends[st.station_id] = await health_trend(session, st.station_id, min(days, 14), 30.0, end)
    sections = [_kpi("stations", len(stations)),
                _table(["station", "overall", "status", "sensors"], rows),
                {"kind": "trends", "trends": trends}]
    return {"title": REPORT_TYPES["station_health"], "window_days": days,
            "summary": f"Health for {len(stations)} stations with 14-day trends.",
            "sections": sections,
            "csv": {"columns": ["station_id", "sensor", "score", "status", "anomalies"], "rows": csv_rows}}


async def maintenance_report(session: AsyncSession, station_id: str | None = None,
                             days: int = 30, end: datetime | None = None) -> dict:
    end = _utc(end or datetime.now(timezone.utc))
    stations = await _stations(session, station_id)
    intel_rows, csv_rows = [], []
    for st in stations:
        for item in await analyze_station(session, st.station_id, 30.0, end):
            intel_rows.append([st.station_id, item.sensor_type, item.health, item.maintenance_risk,
                               item.risk_level, item.maintenance_priority, item.reason[:160]])
            csv_rows.append({"station_id": st.station_id, "sensor": item.sensor_type,
                             "health": item.health, "risk": item.maintenance_risk,
                             "level": item.risk_level, "priority": item.maintenance_priority,
                             "reason": item.reason})
    orders = (await session.execute(
        select(MaintenanceRecommendation).where(MaintenanceRecommendation.status == "OPEN")
        .order_by(desc(MaintenanceRecommendation.id)).limit(100))).scalars().all()
    orders = [o for o in orders if station_id is None or o.station_id == station_id]
    sections = [
        _kpi("sensors_assessed", len(intel_rows)),
        _kpi("high_risk", sum(1 for r in intel_rows if r[4] == "HIGH")),
        _kpi("open_orders", len(orders)),
        _table(["station", "sensor", "health", "risk", "level", "priority", "reason"], intel_rows),
        _table(["id", "station", "priority", "recommendation", "status"],
               [[o.id, o.station_id, o.priority, o.recommendation, o.status] for o in orders]),
    ]
    return {"title": REPORT_TYPES["maintenance"], "window_days": days,
            "summary": f"{len([r for r in intel_rows if r[4] in ('HIGH',)])} high-risk sensors, {len(orders)} open orders.",
            "sections": sections,
            "csv": {"columns": ["station_id", "sensor", "health", "risk", "level", "priority", "reason"],
                    "rows": csv_rows}}


async def regional_quality(session: AsyncSession, station_id: str | None = None,
                           days: int = 7, end: datetime | None = None) -> dict:
    end = _utc(end or datetime.now(timezone.utc))
    stations = await _stations(session, station_id)
    zones: dict[str, list] = {}
    for st in stations:
        zones.setdefault(zone_of(st.latitude), []).append(st)
    rows, csv_rows = [], []
    from backend.app.quality.engine import station_quality as sq_fn
    for zone, sts in sorted(zones.items()):
        scores = []
        for st in sts:
            sq, _ = await sq_fn(session, st.station_id, 24 * days, end)
            scores.append(sq)
        if not scores:
            continue
        mean = lambda f: round(sum(getattr(s, f) for s in scores) / len(scores), 1)
        rows.append([zone, len(sts), mean("completeness"), mean("validity"),
                     mean("consistency"), mean("timeliness"), mean("overall")])
        csv_rows.append({"zone": zone, "stations": len(sts), "overall": mean("overall")})
    sections = [_kpi("zones", len(rows)),
                _table(["zone", "stations", "completeness", "validity", "consistency",
                        "timeliness", "overall"], rows)]
    return {"title": REPORT_TYPES["regional_quality"], "window_days": days,
            "summary": f"Quality across {len(rows)} zones.",
            "sections": sections,
            "csv": {"columns": ["zone", "stations", "overall"], "rows": csv_rows}}


BUILDERS = {"daily_quality": daily_quality, "weekly_anomaly": weekly_anomaly,
            "station_health": station_health_report, "maintenance": maintenance_report,
            "regional_quality": regional_quality}
