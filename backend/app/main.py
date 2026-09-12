"""SKYGUARD AI clean foundation API (SIH 26073). Swagger at /docs."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import router
from backend.app.api.routes_dataset import router as dataset_router
from backend.app.api.routes_explain import router as explain_router
from backend.app.api.routes_maintenance import router as maintenance_router
from backend.app.api.routes_simulation import router as simulation_router
from backend.app.api.routes_spatial import router as spatial_router
from backend.app.api.routes_insights import router as insights_router
from backend.app.api.routes_quality import router as quality_router
from backend.app.api.routes_evaluation import router as evaluation_router
from backend.app.api.routes_system import router as system_router
from backend.app.api.routes_reports import router as reports_router
from backend.app.core.config import settings
from backend.app.database.session import AsyncSessionLocal, close_db, init_db, seed_stations


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.app.simulation.engine import SimulationEngine, seed_baseline_history

    await init_db()
    await seed_stations()
    station_list = [{"station_id": s["station_id"], "latitude": s["latitude"], "longitude": s["longitude"]}
                    for s in settings.STATION_COORDS]
    await seed_baseline_history(AsyncSessionLocal, station_list)
    app.state.sim = SimulationEngine(
        AsyncSessionLocal,
        station_list,
        step_minutes=60, tick_interval_s=1.0, seed=42,
    )
    yield
    try:
        await app.state.sim.stop()
    finally:
        await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations (IMD). Foundation: stations, observations, anomalies, alerts, sensor health.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(_, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", summary="Service liveness", tags=["ops"])
async def health():
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}


app.include_router(router, prefix=settings.API_PREFIX, tags=["skyguard"])
app.include_router(dataset_router, prefix=settings.API_PREFIX, tags=["dataset"])
app.include_router(explain_router, prefix=settings.API_PREFIX, tags=["explanations"])
app.include_router(maintenance_router, prefix=settings.API_PREFIX, tags=["maintenance"])
app.include_router(simulation_router, prefix=settings.API_PREFIX, tags=["simulation"])
app.include_router(spatial_router, prefix=settings.API_PREFIX, tags=["spatial"])
app.include_router(insights_router, prefix=settings.API_PREFIX, tags=["insights"])
app.include_router(quality_router, prefix=settings.API_PREFIX, tags=["data-quality"])
app.include_router(evaluation_router, prefix=settings.API_PREFIX, tags=["evaluation"])
app.include_router(system_router, prefix=settings.API_PREFIX, tags=["system"])
app.include_router(reports_router, prefix=settings.API_PREFIX, tags=["reports"])
app.include_router(simulation_router)  # /ws/live + unversioned control aliases
app.include_router(spatial_router, tags=["spatial-compat"])
app.include_router(insights_router, tags=["insights-compat"])
app.include_router(quality_router, tags=["quality-compat"])
app.include_router(evaluation_router, tags=["evaluation-compat"])
app.include_router(system_router, tags=["system-compat"])
app.include_router(reports_router, tags=["reports-compat"])
# Convenience aliases at the exact paths requested in the task (unversioned)
app.include_router(router, tags=["skyguard-compat"])
app.include_router(dataset_router, tags=["dataset-compat"])
app.include_router(explain_router, tags=["explanations-compat"])
app.include_router(maintenance_router, tags=["maintenance-compat"])

# Single-service production: serve the built frontend (frontend/dist) so one
# deployment hosts UI + API + WebSocket on the same origin. The React app uses
# HashRouter, so serving index.html at / is sufficient (no rewrite rules).
from pathlib import Path as _Path

_DIST = _Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (_DIST / "index.html").exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
