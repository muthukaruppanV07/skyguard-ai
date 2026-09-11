"""Model evaluation API: controlled runs, threshold vs hybrid."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.evaluation.harness import EvalConfig, run_evaluation
from backend.app.models.model_result import ModelResult

router = APIRouter(prefix="/evaluation", tags=["evaluation"])
LAST_RUN: dict | None = None


class RunRequest(BaseModel):
    episodes_per_category: int = Field(default=2, ge=1, le=5)
    history_points: int = Field(default=64, ge=12, le=240)
    test_points: int = Field(default=12, ge=4, le=48)
    step_minutes: int = Field(default=60, ge=5, le=1440)
    seed: int = Field(default=42)


@router.get("/methods", summary="Compared methods and metric definitions")
async def methods():
    return {
        "methods": {
            "threshold": "Traditional QC: physical range gates + per-hour rate gates + stuck-value check.",
            "hybrid": "SkyGuard hybrid AI: 9 fused detectors (physical, statistical, robust-z, rate, isolation forest, temporal, multivariate, frozen, drift).",
        },
        "metrics": ["accuracy", "precision", "recall", "f1", "fpr", "confusion", "latency_steps"],
        "decision_rule": "score >= 50 counts as a positive for both methods.",
    }


@router.post("/run", summary="Run a controlled evaluation (computed live, may take ~1 min)")
async def run(req: RunRequest, db: AsyncSession = Depends(get_db)):
    global LAST_RUN
    cfg = EvalConfig(episodes_per_category=req.episodes_per_category,
                     history_points=req.history_points, test_points=req.test_points,
                     step_minutes=req.step_minutes, seed=req.seed)
    result = run_evaluation(cfg)
    result["ran_at"] = datetime.now(timezone.utc).isoformat()
    LAST_RUN = result
    for name in ("threshold", "hybrid"):
        m = result["methods"][name]
        db.add(ModelResult(model_name=f"eval_{name}", version="1.0.0", metric_name="f1",
                           metric_value=m["f1"],
                           details=json.dumps({"accuracy": m["accuracy"], "precision": m["precision"],
                                               "recall": m["recall"], "fpr": m["fpr"],
                                               "episodes": result["episodes"]})[:2000]))
    await db.commit()
    return result


@router.get("/latest", summary="Most recent evaluation run in this process")
async def latest():
    if LAST_RUN is None:
        raise HTTPException(status_code=404, detail="No evaluation run yet; POST /evaluation/run first")
    return LAST_RUN
