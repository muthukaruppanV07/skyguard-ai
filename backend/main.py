from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database.session import init_db, close_db
from backend.api import routes_stations, routes_readings, routes_anomalies, routes_health, routes_simulate, routes_detect, routes_explain, routes_models, routes_statistics, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_stations.router, prefix="/api", tags=["stations"])
app.include_router(routes_readings.router, prefix="/api", tags=["readings"])
app.include_router(routes_anomalies.router, prefix="/api", tags=["anomalies"])
app.include_router(routes_health.router, prefix="/api", tags=["health"])
app.include_router(routes_simulate.router, prefix="/api", tags=["simulation"])
app.include_router(routes_detect.router, prefix="/api", tags=["detection"])
app.include_router(routes_explain.router, prefix="/api", tags=["explainability"])
app.include_router(routes_models.router, prefix="/api", tags=["models"])
app.include_router(routes_statistics.router, prefix="/api", tags=["statistics"])
app.include_router(websocket.router, tags=["websocket"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        workers=settings.API_WORKERS,
    )