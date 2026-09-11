"""Simulation controls (REST) + real-time stream (WebSocket)."""

import json as _json

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.simulation.engine import SCENARIO_INFO

router = APIRouter(tags=["simulation"])


def get_sim(request: Request):
    sim = getattr(request.app.state, "sim", None)
    if sim is None:
        raise HTTPException(status_code=503, detail="Simulation engine not initialised")
    return sim


class InjectRequest(BaseModel):
    scenario_id: str
    station_ids: list[str] | None = None
    duration_ticks: int | None = Field(default=None, ge=1, le=1000)
    magnitude: float = Field(default=1.0, ge=0.1, le=5.0)


@router.get("/simulation/scenarios", summary="List injection scenarios")
async def list_scenarios():
    return [{"id": k, "description": v} for k, v in SCENARIO_INFO.items()]


@router.get("/simulation/status", summary="Engine state")
async def status(request: Request):
    sim = get_sim(request)
    return {"status": sim.status, "tick": sim.tick_count,
            "scenario": sim.active.scenario_id if sim.active else None,
            "stations": list(sim.stations)}


@router.post("/simulation/start", summary="START streaming")
async def start(request: Request):
    get_sim(request).start()
    return {"status": get_sim(request).status}


@router.post("/simulation/pause", summary="PAUSE streaming")
async def pause(request: Request):
    get_sim(request).pause()
    return {"status": get_sim(request).status}


@router.post("/simulation/resume", summary="Resume after pause")
async def resume(request: Request):
    get_sim(request).resume()
    return {"status": get_sim(request).status}


@router.post("/simulation/stop", summary="STOP streaming")
async def stop(request: Request):
    await get_sim(request).stop()
    return {"status": get_sim(request).status}


@router.post("/simulation/reset", summary="RESET scenario and clock")
async def reset(request: Request):
    get_sim(request).reset()
    return {"status": get_sim(request).status, "tick": 0}


@router.post("/simulation/inject", summary="INJECT scenario")
async def inject(req: InjectRequest, request: Request):
    try:
        get_sim(request).inject(req.scenario_id, req.station_ids, req.duration_ticks, req.magnitude)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    sim = get_sim(request)
    return {"scenario": sim.active.scenario_id, "targets": sim.active.targets,
            "ticks_left": sim.active.ticks_left}


@router.post("/simulation/tick", summary="Advance one step manually")
async def manual_tick(request: Request):
    return await get_sim(request).tick()


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    sim = getattr(websocket.app.state, "sim", None)
    if sim is None:
        await websocket.send_json({"type": "error", "detail": "sim not initialised"})
        await websocket.close()
        return
    q = sim.subscribe()
    await websocket.send_json({"type": "snapshot", "status": sim.status,
                               "tick": sim.tick_count, "stations": list(sim.stations)})
    try:
        while True:
            import asyncio as _aio

            try:
                msg = await _aio.wait_for(q.get(), timeout=0.2)
                await websocket.send_text(_json.dumps(msg, default=str))
            except _aio.TimeoutError:
                pass
            try:
                cmd = await _aio.wait_for(websocket.receive_json(), timeout=0.01)
            except _aio.TimeoutError:
                continue
            action = (cmd.get("cmd") or "").lower()
            if action == "start":
                sim.start()
            elif action == "pause":
                sim.pause()
            elif action == "resume":
                sim.resume()
            elif action == "stop":
                await sim.stop()
            elif action == "reset":
                sim.reset()
            elif action == "inject":
                try:
                    sim.inject(cmd.get("scenario_id", ""), cmd.get("station_ids"),
                               cmd.get("duration_ticks"), cmd.get("magnitude", 1.0))
                except ValueError as exc:
                    await websocket.send_json({"type": "error", "detail": str(exc)})
                    continue
            else:
                await websocket.send_json({"type": "error", "detail": f"unknown cmd {action!r}"})
                continue
            await websocket.send_json({"type": "ack", "cmd": action, "status": sim.status})
    except WebSocketDisconnect:
        pass
    finally:
        sim.unsubscribe(q)
