from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Literal
from backend.database.session import get_db
from backend.simulation.anomaly_injector import AnomalyInjector
from backend.config import ANOMALY_INJECTION_TYPES

router = APIRouter(prefix="/simulate", tags=["simulation"])


class AnomalyInjectionRequest(BaseModel):
    station_id: str
    fault_type: Literal[tuple(ANOMALY_INJECTION_TYPES)]
    params: dict = {}


class AdvancedActionRequest(BaseModel):
    action: str
    params: dict = {}


@router.post("/anomaly")
async def inject_anomaly(request: AnomalyInjectionRequest, db: AsyncSession = Depends(get_db)):
    injector = AnomalyInjector(db)
    result = await injector.inject(
        station_id=request.station_id,
        fault_type=request.fault_type,
        params=request.params,
    )
    return result


@router.post("/reset")
async def reset_simulation(db: AsyncSession = Depends(get_db)):
    from backend.simulation.aws_simulator import AWSSimulator
    simulator = AWSSimulator(db)
    await simulator.reset()
    return {"status": "reset", "message": "Simulator reset to healthy state"}


@router.post("/advanced")
async def advanced_action(request: AdvancedActionRequest, db: AsyncSession = Depends(get_db)):
    from backend.simulation.advanced_demo import AdvancedSIHDemo
    injector = AnomalyInjector(db)
    demo = AdvancedSIHDemo(injector)
    result = await demo.run_step_by_action(request.action, request.params)
    return result