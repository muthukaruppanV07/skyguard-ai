from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Set
import asyncio
import json
from backend.database.session import get_db
from backend.database.repositories import ReadingRepository, AnomalyRepository, SensorHealthRepository
from backend.services.ingestion import IngestionService

router = APIRouter()

active_connections: Set[WebSocket] = set()


async def broadcast_live_data():
    while True:
        if active_connections:
            from backend.database.session import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                ingestion = IngestionService(db)
                data = await ingestion.get_live_snapshot()
                
                message = json.dumps({
                    "type": "live_update",
                    "timestamp": data["timestamp"],
                    "stations": data["stations"],
                })
                
                disconnected = set()
                for ws in active_connections:
                    try:
                        await ws.send_text(message)
                    except:
                        disconnected.add(ws)
                
                for ws in disconnected:
                    active_connections.discard(ws)
        
        await asyncio.sleep(1)


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    active_connections.add(websocket)
    
    try:
        # Send initial snapshot
        ingestion = IngestionService(db)
        data = await ingestion.get_live_snapshot()
        await websocket.send_text(json.dumps({
            "type": "initial_snapshot",
            "timestamp": data["timestamp"],
            "stations": data["stations"],
        }))
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)