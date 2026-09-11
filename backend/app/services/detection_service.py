"""Detection service: run the hybrid engine on DB history and persist results."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.detection.engine import DetectionResult, HybridEngine
from backend.app.detection.event_classifier import (
    classify_event,
    guard_check,
    haversine_km,
)
from backend.app.models.anomaly import Anomaly
from backend.app.models.observation import Observation
from backend.app.models.sensor_health import SensorHealth
from backend.app.models.station import Station


def _row_dict(o: Observation) -> dict:
    return {
        "timestamp": o.timestamp,
        "temperature": o.temperature,
        "pressure": o.pressure,
        "humidity": o.humidity,
    }


async def load_history(session: AsyncSession, station_id: str, limit: int = 240) -> list[dict]:
    stmt = (
        select(Observation)
        .where(Observation.station_id == station_id)
        .order_by(desc(Observation.timestamp))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_dict(o) for o in reversed(rows)]


async def load_neighbors(
    session: AsyncSession,
    station_id: str,
    timestamp: datetime,
    radius_km: float = 150.0,
    max_age_hours: float = 6.0,
    history_limit: int = 48,
) -> tuple[list[dict], dict, dict[str, list[dict]]]:
    """Latest nearby-station readings + target coords + neighbour histories."""
    stations = (await session.execute(select(Station))).scalars().all()
    target = next((s for s in stations if s.station_id == station_id), None)
    if target is None:
        raise ValueError(f"Unknown station_id: {station_id}")
    coords = {"latitude": target.latitude, "longitude": target.longitude}
    neighbors: list[dict] = []
    neighbor_histories: dict[str, list[dict]] = {}
    for s in stations:
        if s.station_id in (station_id, "SYSTEM"):
            continue
        if haversine_km(target.latitude, target.longitude, s.latitude, s.longitude) > radius_km:
            continue
        stmt = (
            select(Observation)
            .where(Observation.station_id == s.station_id, Observation.timestamp <= timestamp)
            .order_by(desc(Observation.timestamp))
            .limit(1)
        )
        obs = (await session.execute(stmt)).scalars().first()
        if obs is None:
            continue
        obs_ts = obs.timestamp if obs.timestamp.tzinfo else obs.timestamp.replace(tzinfo=timestamp.tzinfo)
        age_h = abs((timestamp - obs_ts).total_seconds()) / 3600.0
        if age_h > max_age_hours:
            continue
        neighbors.append(
            {
                "station_id": s.station_id,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "temperature": obs.temperature,
                "pressure": obs.pressure,
                "humidity": obs.humidity,
            }
        )
        hstmt = (
            select(Observation)
            .where(Observation.station_id == s.station_id, Observation.timestamp <= timestamp)
            .order_by(desc(Observation.timestamp))
            .limit(history_limit)
        )
        hrows = (await session.execute(hstmt)).scalars().all()
        neighbor_histories[s.station_id] = [_row_dict(o) for o in reversed(hrows)]
    return neighbors, coords, neighbor_histories


async def load_sensor_health(session: AsyncSession, station_id: str) -> dict:
    rows = (
        await session.execute(select(SensorHealth).where(SensorHealth.station_id == station_id))
    ).scalars().all()
    return {r.sensor_type: r.score for r in rows}


async def raise_alert(session: AsyncSession, station_id: str, anomaly_id: int,
                      severity: str, message: str):
    """Persist an operator alert for a stored anomaly."""
    from backend.app.models.alert import Alert

    alert = Alert(station_id=station_id, anomaly_id=anomaly_id,
                  severity=severity, message=message)
    session.add(alert)
    await session.flush()
    return alert


async def persist_detection(
    session: AsyncSession,
    station_id: str,
    timestamp: datetime,
    result: DetectionResult,
    classification,
    guard,
    explanation,
    observation_id: int | None = None,
) -> Anomaly:
    """Build + store the anomaly row (classification/explanation embedded)."""
    evidence = dict(result.evidence)
    evidence["classification"] = {
        "event_type": classification.event_type,
        "sensor_fault_probability": classification.sensor_fault_probability,
        "weather_event_probability": classification.weather_event_probability,
        "spatial_consistency": classification.spatial_consistency,
        "temporal_consistency": classification.temporal_consistency,
        "multivariate_consistency": classification.multivariate_consistency,
        "reasoning": classification.reasoning,
    }
    evidence["guard"] = {
        "verdict": guard.verdict,
        "recommend_suppress": guard.recommend_suppress,
        "passed": guard.passed,
        "failed": guard.failed,
    }
    from backend.app.explainability.explainer import compact_explanation

    evidence["explanation"] = compact_explanation(explanation)
    row = Anomaly(
        station_id=station_id,
        observation_id=observation_id,
        timestamp=timestamp,
        score=result.anomaly_score,
        severity=result.severity,
        root_cause=result.anomaly_type,
        message=f"{station_id}: {result.anomaly_type} score={result.anomaly_score}",
        confidence=result.confidence,
        anomaly_type=result.anomaly_type,
        detector_results=json.dumps(
            [
                {"name": r.name, "score": r.score, "triggered": r.triggered, "candidate": r.candidate_type}
                for r in result.detector_results
            ]
        )[:4000],
        evidence=json.dumps(evidence)[:4000],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def detect_and_store(
    session: AsyncSession,
    station_id: str,
    timestamp: datetime,
    temperature: float | None,
    pressure: float | None,
    humidity: float | None,
    engine: HybridEngine | None = None,
    observation_id: int | None = None,
    history_limit: int = 240,
    neighbors: list[dict] | None = None,
    sensor_health: dict | None = None,
    neighbor_histories: dict[str, list[dict]] | None = None,
    auto_neighbors: bool = False,
) -> tuple[DetectionResult, Anomaly | None]:
    """Run detection, classify event vs fault, guard, and store non-NORMAL outcomes."""
    station = await session.get(Station, station_id)
    if station is None:
        raise ValueError(f"Unknown station_id: {station_id}")
    history = await load_history(session, station_id, history_limit)
    eng = engine or HybridEngine()
    current = {"timestamp": timestamp, "temperature": temperature, "pressure": pressure, "humidity": humidity}
    result = eng.detect(current, history)
    row: Anomaly | None = None
    if result.anomaly_type != "NORMAL":
        nb = neighbors
        sh = sensor_health
        nh = neighbor_histories
        if auto_neighbors:
            try:
                nb, _, nh = await load_neighbors(session, station_id, timestamp)
            except ValueError:
                nb, nh = [], {}
        if sh is None and auto_neighbors:
            sh = await load_sensor_health(session, station_id)
        classification = classify_event(current, history, result, neighbors=nb, sensor_health=sh,
                                        neighbor_histories=nh)
        guard = guard_check(current, history, result, neighbors=nb, sensor_health=sh)
        from backend.app.explainability.explainer import build_explanation

        explanation = build_explanation(current, history, result, classification, guard, neighbors=nb)
        row = await persist_detection(session, station_id, timestamp, result,
                                      classification, guard, explanation, observation_id)
    return result, row
