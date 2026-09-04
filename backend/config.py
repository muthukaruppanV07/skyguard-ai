import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "SKYGUARD AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1

    DATABASE_URL: str = "sqlite+aiosqlite:///./skyguard.db"
    DATABASE_ECHO: bool = False

    SIMULATOR_STATIONS: int = 8
    SIMULATOR_INTERVAL_SECONDS: int = 1
    SIMULATOR_START_DATE: str = "2026-01-01"
    SIMULATOR_DAYS: int = 30

    STATION_COORDS: List[dict] = [
        {"station_id": "AWS001", "latitude": 28.6139, "longitude": 77.2090, "elevation": 216.0, "name": "New Delhi"},
        {"station_id": "AWS002", "latitude": 19.0760, "longitude": 72.8777, "elevation": 14.0, "name": "Mumbai"},
        {"station_id": "AWS003", "latitude": 12.9716, "longitude": 77.5946, "elevation": 920.0, "name": "Bangalore"},
        {"station_id": "AWS004", "latitude": 13.0827, "longitude": 80.2707, "elevation": 6.7, "name": "Chennai"},
        {"station_id": "AWS005", "latitude": 22.5726, "longitude": 88.3639, "elevation": 9.0, "name": "Kolkata"},
        {"station_id": "AWS006", "latitude": 17.3850, "longitude": 78.4867, "elevation": 505.0, "name": "Hyderabad"},
        {"station_id": "AWS007", "latitude": 18.5204, "longitude": 73.8567, "elevation": 560.0, "name": "Pune"},
        {"station_id": "AWS008", "latitude": 23.0225, "longitude": 72.5714, "elevation": 53.0, "name": "Ahmedabad"},
    ]

    TEMP_MIN: float = -10.0
    TEMP_MAX: float = 50.0
    PRESSURE_MIN: float = 850.0
    PRESSURE_MAX: float = 1100.0
    HUMIDITY_MIN: float = 0.0
    HUMIDITY_MAX: float = 100.0

    MAX_TEMP_CHANGE_PER_MIN: float = 2.0
    MAX_PRESSURE_CHANGE_PER_MIN: float = 5.0
    MAX_HUMIDITY_CHANGE_PER_MIN: float = 5.0

    FROZEN_THRESHOLD_MINUTES: int = 30
    MISSING_THRESHOLD_MINUTES: int = 10

    RULE_WEIGHT: float = 0.15
    ISOLATION_FOREST_WEIGHT: float = 0.25
    AUTOENCODER_WEIGHT: float = 0.25
    TEMPORAL_WEIGHT: float = 0.15
    MULTIVARIATE_WEIGHT: float = 0.10
    SPATIAL_WEIGHT: float = 0.10

    ANOMALY_THRESHOLD_LOW: int = 30
    ANOMALY_THRESHOLD_SUSPICIOUS: int = 50
    ANOMALY_THRESHOLD_HIGH: int = 70
    ANOMALY_THRESHOLD_CRITICAL: int = 85

    IF_CONTAMINATION: float = 0.01
    IF_N_ESTIMATORS: int = 200
    IF_MAX_SAMPLES: str = "auto"
    IF_RANDOM_STATE: int = 42

    AE_INPUT_DIM: int = 30
    AE_ENCODING_DIM: int = 8
    AE_HIDDEN_DIMS: List[int] = [16]
    AE_LEARNING_RATE: float = 1e-3
    AE_EPOCHS: int = 50
    AE_BATCH_SIZE: int = 64
    AE_DROPOUT: float = 0.1

    TEMPORAL_WINDOW_MINUTES: int = 60
    TEMPORAL_ZSCORE_THRESHOLD: float = 3.0
    DRIFT_WINDOW_HOURS: int = 24
    DRIFT_THRESHOLD_PER_HOUR: float = 0.5

    MULTIVARIATE_TEMP_HUMIDITY_CORR: float = -0.7
    MULTIVARIATE_PRESSURE_TEMP_CORR: float = 0.3
    MULTIVARIATE_THRESHOLD: float = 2.5

    SPATIAL_K_NEIGHBORS: int = 3
    SPATIAL_MAX_DISTANCE_KM: float = 150.0
    SPATIAL_WEIGHT_DECAY: float = 1.5
    SPATIAL_THRESHOLD: float = 2.0

    ROOT_CAUSE_CONFIDENCE_THRESHOLD: float = 0.7

    SHAP_SAMPLE_SIZE: int = 100
    SHAP_MAX_DISPLAY: int = 10

    HEALTH_WINDOW_DAYS: int = 7
    HEALTH_ANOMALY_WEIGHT: float = 0.3
    HEALTH_DRIFT_WEIGHT: float = 0.2
    HEALTH_FROZEN_WEIGHT: float = 0.15
    HEALTH_MISSING_WEIGHT: float = 0.15
    HEALTH_COMM_WEIGHT: float = 0.1
    HEALTH_RECON_WEIGHT: float = 0.1

    HEALTH_HEALTHY_THRESHOLD: int = 80
    HEALTH_WARNING_THRESHOLD: int = 60
    HEALTH_CRITICAL_THRESHOLD: int = 40

    CORRECTION_WINDOW_HOURS: int = 24
    CORRECTION_MIN_SAMPLES: int = 50
    CORRECTION_CONFIDENCE_THRESHOLD: float = 0.6

    MODEL_DIR: str = "./models"
    MODEL_VERSION: str = "1.0.0"

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

MODEL_DIR = Path(settings.MODEL_DIR)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

ISOLATION_FOREST_PATH = MODEL_DIR / "isolation_forest.joblib"
AUTOENCODER_PATH = MODEL_DIR / "autoencoder.pt"
SCALER_PATH = MODEL_DIR / "scaler.joblib"

SEVERITY_LEVELS = {
    "NORMAL": (0, 30),
    "LOW": (30, 50),
    "SUSPICIOUS": (50, 70),
    "HIGH": (70, 85),
    "CRITICAL": (85, 100),
}

SEVERITY_COLORS = {
    "NORMAL": "#22c55e",
    "LOW": "#84cc16",
    "SUSPICIOUS": "#facc15",
    "HIGH": "#f97316",
    "CRITICAL": "#ef4444",
}

ROOT_CAUSE_TYPES = [
    "NORMAL",
    "TEMPERATURE_SPIKE",
    "PRESSURE_SPIKE",
    "HUMIDITY_SPIKE",
    "SENSOR_DRIFT",
    "FROZEN_SENSOR",
    "MISSING_DATA",
    "DUPLICATE_DATA",
    "COMMUNICATION_FAILURE",
    "MULTIVARIATE_INCONSISTENCY",
    "POSSIBLE_SENSOR_MALFUNCTION",
    "POSSIBLE_REAL_WEATHER_EVENT",
]

SENSOR_TYPES = ["TEMPERATURE", "PRESSURE", "HUMIDITY"]

ANOMALY_INJECTION_TYPES = [
    "TEMPERATURE_SPIKE",
    "PRESSURE_SPIKE",
    "HUMIDITY_SPIKE",
    "TEMPERATURE_DRIFT",
    "PRESSURE_DRIFT",
    "HUMIDITY_DRIFT",
    "FROZEN_SENSOR",
    "MISSING_OBSERVATIONS",
    "DUPLICATE_OBSERVATIONS",
    "COMMUNICATION_FAILURE",
    "RANDOM_NOISE",
    "MULTIVARIATE_INCONSISTENCY",
    "SENSOR_DEGRADATION",
]

FEATURE_COLUMNS = [
    "temperature",
    "pressure",
    "humidity",
    "temp_change",
    "pressure_change",
    "humidity_change",
    "temp_rolling_mean_5",
    "temp_rolling_std_5",
    "pressure_rolling_mean_5",
    "pressure_rolling_std_5",
    "humidity_rolling_mean_5",
    "humidity_rolling_std_5",
    "temp_rolling_min_5",
    "temp_rolling_max_5",
    "pressure_rolling_min_5",
    "pressure_rolling_max_5",
    "humidity_rolling_min_5",
    "humidity_rolling_max_5",
    "temp_rate_of_change",
    "pressure_rate_of_change",
    "humidity_rate_of_change",
    "temp_zscore_60",
    "pressure_zscore_60",
    "humidity_zscore_60",
    "temp_deviation_expected",
    "pressure_deviation_expected",
    "humidity_deviation_expected",
    "hour",
    "day_of_year",
    "season_sin",
    "season_cos",
    "temp_humidity_ratio",
    "pressure_temp_ratio",
]

MODEL_FEATURE_COLUMNS = [c for c in FEATURE_COLUMNS if c not in ["temperature", "pressure", "humidity", "hour", "day_of_year", "season_sin", "season_cos", "temp_humidity_ratio", "pressure_temp_ratio"]]

WEIGHTS_SUM = (
    settings.RULE_WEIGHT
    + settings.ISOLATION_FOREST_WEIGHT
    + settings.AUTOENCODER_WEIGHT
    + settings.TEMPORAL_WEIGHT
    + settings.MULTIVARIATE_WEIGHT
    + settings.SPATIAL_WEIGHT
)

assert abs(WEIGHTS_SUM - 1.0) < 0.001, f"Fusion weights must sum to 1.0, got {WEIGHTS_SUM}"