from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "SkyGuard AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite:///./skyguard.db"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Simulation
    SIMULATION_INTERVAL_SECONDS: int = 5
    NUM_STATIONS: int = 5
    STATION_IDS: List[str] = ["AWS001", "AWS002", "AWS003", "AWS004", "AWS005"]

    # Station coordinates (lat, lon) - simulated for Delhi NCR region
    STATION_COORDINATES: dict = {
        "AWS001": (28.6139, 77.2090),
        "AWS002": (28.7041, 77.1025),
        "AWS003": (28.5355, 77.3910),
        "AWS004": (28.4089, 77.3178),
        "AWS005": (28.6692, 77.4538),
    }

    # Anomaly Detection Thresholds
    TEMP_MIN: float = -10.0
    TEMP_MAX: float = 50.0
    HUMIDITY_MIN: float = 0.0
    HUMIDITY_MAX: float = 100.0
    PRESSURE_MIN: float = 900.0
    PRESSURE_MAX: float = 1100.0

    # Rate of change thresholds (per minute)
    MAX_TEMP_RATE: float = 2.0
    MAX_HUMIDITY_RATE: float = 5.0
    MAX_PRESSURE_RATE: float = 1.0

    # Frozen sensor detection
    FROZEN_THRESHOLD_MINUTES: int = 10
    FROZEN_TOLERANCE: float = 0.01

    # ML Model Paths
    MODEL_DIR: str = "./models"
    ISOLATION_FOREST_PATH: str = "./models/isolation_forest.pkl"
    AUTOENCODER_PATH: str = "./models/autoencoder.pt"

    # Anomaly Fusion Weights
    WEIGHT_RULE_BASED: float = 0.15
    WEIGHT_ISOLATION_FOREST: float = 0.25
    WEIGHT_AUTOENCODER: float = 0.25
    WEIGHT_TEMPORAL: float = 0.15
    WEIGHT_MULTIVARIATE: float = 0.10
    WEIGHT_SPATIAL: float = 0.10

    # Anomaly Score Thresholds
    SCORE_NORMAL_MAX: float = 30.0
    SCORE_LOW_MAX: float = 50.0
    SCORE_SUSPICIOUS_MAX: float = 70.0
    SCORE_HIGH_MAX: float = 85.0

    # Sensor Health
    HEALTH_WINDOW_HOURS: int = 24
    HEALTH_CRITICAL_THRESHOLD: float = 50.0
    HEALTH_WARNING_THRESHOLD: float = 75.0

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30

    # Demo Mode
    DEMO_MODE: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()