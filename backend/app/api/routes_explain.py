"""Explanation API: stored WHY for an anomaly + live preview without storing."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.detection.engine import HybridEngine
from backend.app.detection.event_classifier import classify_event, guard_check
from backend.app.explainability.explainer import build_explanation
from backend.app.models.anomaly import Anomaly
from backend.app.models.observation import Observation
from backend.app.services.detection_service import (
    detect_and_store,
    load_history,
    load_neighbors,
    load_sensor_health,
)

router = APIRouter(prefix="/explanations", tags=["explanations"])


class PreviewRequest(BaseModel):
    station_id: str = Field(min_length=1, max_length=20)
    timestamp: datetime
    temperature: float | None = Field(default=None, ge=settings.TEMP_MIN, le=settings.TEMP_MAX)
    pressure: float | None = Field(default=None, ge=settings.PRESSURE_MIN, le=settings.PRESSURE_MAX)
    humidity: float | None = Field(default=None, ge=settings.HUMIDITY_MIN, le=settings.HUMIDITY_MAX)


def _exp_to_dict(exp) -> dict:
    return {
        "station_id": exp.station_id,
        "anomaly_type": exp.anomaly_type,
        "anomaly_score": exp.anomaly_score,
        "severity": exp.severity,
        "confidence": exp.confidence,
        "root_cause": exp.root_cause,
        "event_type": exp.event_type,
        "main_reason": exp.main_reason,
        "conclusion": exp.conclusion,
        "supporting_evidence": exp.supporting_evidence,
        "contributing_features": exp.contributing_features,
        "methods_triggered": exp.methods_triggered,
        "recommended_action": exp.recommended_action,
        "attribution_method": exp.attribution_method,
        "shap_available": exp.shap_available,
    }


@router.get("/{anomaly_id}", summary="WHY was this flagged? Stored + live explanation")
async def get_explanation(anomaly_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(Anomaly, anomaly_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    try:
        stored = json.loads(row.evidence or "{}")
    except json.JSONDecodeError:
        stored = {}
    live = None
    if row.observation_id is not None:
        obs = await db.get(Observation, row.observation_id)
        if obs is not None:
            history = await load_history(db, row.station_id)
            # Exclude the observation itself from history if present
            history = [h for h in history if h["timestamp"] != obs.timestamp]
            current = {"timestamp": obs.timestamp, "temperature": obs.temperature,
                       "pressure": obs.pressure, "humidity": obs.humidity,
                       "station_id": row.station_id}
            eng = HybridEngine()
            result = eng.detect(current, history)
            try:
                nb, _, nh = await load_neighbors(db, row.station_id, obs.timestamp)
                sh = await load_sensor_health(db, row.station_id)
            except ValueError:
                nb, nh, sh = [], {}, None
            cls = classify_event(current, history, result, neighbors=nb, sensor_health=sh,
                                 neighbor_histories=nh)
            guard = guard_check(current, history, result, neighbors=nb, sensor_health=sh)
            live = _exp_to_dict(build_explanation(current, history, result, cls, guard, neighbors=nb))
    return {"anomaly_id": row.id,
            "stored": stored.get("explanation"),
            "stored_classification": stored.get("classification"),
            "stored_guard": stored.get("guard"),
            "live": live}


@router.post("/preview", summary="Explain a hypothetical reading without storing")
async def preview(req: PreviewRequest, db: AsyncSession = Depends(get_db)):
    from backend.app.models.station import Station

    if await db.get(Station, req.station_id) is None:
        raise HTTPException(status_code=404, detail=f"Station {req.station_id} not found")
    history = await load_history(db, req.station_id)
    current = {"timestamp": req.timestamp, "temperature": req.temperature,
               "pressure": req.pressure, "humidity": req.humidity, "station_id": req.station_id}
    result = HybridEngine().detect(current, history)
    try:
        nb, _, nh = await load_neighbors(db, req.station_id, req.timestamp)
        sh = await load_sensor_health(db, req.station_id)
    except ValueError:
        nb, nh, sh = [], {}, None
    cls = classify_event(current, history, result, neighbors=nb, sensor_health=sh, neighbor_histories=nh)
    guard = guard_check(current, history, result, neighbors=nb, sensor_health=sh)
    exp = build_explanation(current, history, result, cls, guard, neighbors=nb)
    return _exp_to_dict(exp)


@router.post("/detect-and-explain", summary="Run full pipeline and return explanation (stores anomaly)")
async def detect_and_explain(req: PreviewRequest, db: AsyncSession = Depends(get_db)):
    from backend.app.models.observation import Observation
    from backend.app.models.station import Station

    if await db.get(Station, req.station_id) is None:
        raise HTTPException(status_code=404, detail=f"Station {req.station_id} not found")
    obs = Observation(station_id=req.station_id, timestamp=req.timestamp,
                      temperature=req.temperature, pressure=req.pressure, humidity=req.humidity)
    db.add(obs)
    await db.flush()
    result, row = await detect_and_store(
        db, req.station_id, req.timestamp, req.temperature, req.pressure, req.humidity,
        observation_id=obs.id, auto_neighbors=True,
    )
    await db.commit()
    if row is None:
        return {"stored": False, "anomaly_type": result.anomaly_type,
                "anomaly_score": result.anomaly_score}
    try:
        stored = json.loads(row.evidence or "{}")
    except json.JSONDecodeError:
        stored = {}
    return {"stored": True, "anomaly_id": row.id, "explanation": stored.get("explanation"),
            "classification": stored.get("classification"), "guard": stored.get("guard")}
