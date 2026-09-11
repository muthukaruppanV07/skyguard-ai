"""SKYGUARD AI — clean foundation config (SIH 26073, MoES/IMD)."""

from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SKYGUARD AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    API_PREFIX: str = "/api/v1"

    # Separate clean DB so the new foundation does not clobber legacy skyguard.db
    DATABASE_URL: str = "sqlite+aiosqlite:///./skyguard_app.db"
    DATABASE_ECHO: bool = False

    # IMD physical plausibility ranges (core inputs: T/P/H)
    TEMP_MIN: float = -10.0
    TEMP_MAX: float = 50.0
    PRESSURE_MIN: float = 850.0
    PRESSURE_MAX: float = 1100.0
    HUMIDITY_MIN: float = 0.0
    HUMIDITY_MAX: float = 100.0

    # Rule-based anomaly score thresholds (0-100 unified score)
    ANOMALY_THRESHOLD_SUSPICIOUS: float = 50.0
    ANOMALY_THRESHOLD_HIGH: float = 70.0
    ANOMALY_THRESHOLD_CRITICAL: float = 85.0

    # 8 default AWS stations (seed data)
    STATION_COORDS: List[dict] = [
        {"station_id": "AWS001", "name": "New Delhi", "latitude": 28.6139, "longitude": 77.2090},
        {"station_id": "AWS002", "name": "Mumbai", "latitude": 19.0760, "longitude": 72.8777},
        {"station_id": "AWS003", "name": "Bangalore", "latitude": 12.9716, "longitude": 77.5946},
        {"station_id": "AWS004", "name": "Chennai", "latitude": 13.0827, "longitude": 80.2707},
        {"station_id": "AWS005", "name": "Kolkata", "latitude": 22.5726, "longitude": 88.3639},
        {"station_id": "AWS006", "name": "Hyderabad", "latitude": 17.3850, "longitude": 78.4867},
        {"station_id": "AWS007", "name": "Pune", "latitude": 18.5204, "longitude": 73.8567},
        {"station_id": "AWS008", "name": "Ahmedabad", "latitude": 23.0225, "longitude": 72.5714},
    ]

    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
