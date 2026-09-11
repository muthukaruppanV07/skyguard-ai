"""Generated reports API: preview (no store), generate (persist), export file."""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.models.report_run import ReportRun
from backend.app.reports.generator import BUILDERS, REPORT_TYPES

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportRequest(BaseModel):
    report_type: str
    station_id: str | None = None
    days: int = Field(default=7, ge=1, le=90)


def _check(req: ReportRequest) -> None:
    if req.report_type not in BUILDERS:
        raise HTTPException(status_code=400, detail=f"Unknown report_type; one of {', '.join(BUILDERS)}")


async def _build(db: AsyncSession, req: ReportRequest) -> dict:
    _check(req)
    try:
        report = await BUILDERS[req.report_type](db, req.station_id, req.days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    report["report_type"] = req.report_type
    report["params"] = {"station_id": req.station_id, "days": req.days}
    return report


@router.get("/types", summary="Available report types")
async def types():
    return [{"id": k, "title": v} for k, v in REPORT_TYPES.items()]


@router.post("/preview", summary="Build a report without storing")
async def preview(req: ReportRequest, db: AsyncSession = Depends(get_db)):
    return await _build(db, req)


@router.post("/generate", summary="Build and persist a report run")
async def generate(req: ReportRequest, db: AsyncSession = Depends(get_db)):
    report = await _build(db, req)
    row = ReportRun(report_type=req.report_type,
                    params=json.dumps(report["params"]),
                    payload=json.dumps(report)[:60000])
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "report_type": row.report_type,
            "created_at": row.created_at.isoformat() if hasattr(row.created_at, "isoformat") else str(row.created_at),
            "report": report}


@router.get("", summary="List persisted report runs")
async def list_runs(limit: int = Query(default=20, ge=1, le=200),
                     db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ReportRun).order_by(desc(ReportRun.id)).limit(limit))).scalars().all()
    return [{"id": r.id, "report_type": r.report_type, "params": json.loads(r.params),
             "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
             "summary": json.loads(r.payload).get("summary", "")} for r in rows]


@router.get("/{run_id}", summary="Fetch a persisted report")
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(ReportRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Report {run_id} not found")
    return {"id": row.id, "report_type": row.report_type, "params": json.loads(row.params),
            "created_at": row.created_at.isoformat() if hasattr(row.created_at, "isoformat") else str(row.created_at),
            "report": json.loads(row.payload)}


@router.get("/{run_id}/export", summary="Download a report as JSON or CSV")
async def export(run_id: int, format: str = Query(default="json", pattern="^(json|csv)$"),
                 db: AsyncSession = Depends(get_db)):
    row = await db.get(ReportRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Report {run_id} not found")
    report = json.loads(row.payload)
    if format == "json":
        return PlainTextResponse(json.dumps(report, indent=2), media_type="application/json",
                                 headers={"Content-Disposition": f"attachment; filename=report-{run_id}.json"})
    spec = report.get("csv", {"columns": [], "rows": []})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=spec["columns"])
    w.writeheader()
    for r in spec["rows"]:
        w.writerow({c: r.get(c, "") for c in spec["columns"]})
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=report-{run_id}.csv"})
