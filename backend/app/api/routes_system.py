"""Judge-mode system transparency API."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.system.info import get_system_info

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", summary="Live system facts for technical judges")
async def system_info(request: Request, db: AsyncSession = Depends(get_db)):
    sim = getattr(request.app.state, "sim", None)
    return await get_system_info(db, sim)
