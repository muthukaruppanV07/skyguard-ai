"""AI insights API: data-grounded fleet insights."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.insights.generator import generate_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", summary="Fleet insights generated from live data")
async def list_insights(hours: int = Query(default=24, ge=1, le=168),
                        db: AsyncSession = Depends(get_db)):
    insights = await generate_insights(db, hours)
    return [
        {"id": i.id, "kind": i.kind, "title": i.title, "evidence": i.evidence,
         "affected_stations": i.affected_stations, "confidence": i.confidence,
         "recommended_action": i.recommended_action, "severity": i.severity}
        for i in insights
    ]
