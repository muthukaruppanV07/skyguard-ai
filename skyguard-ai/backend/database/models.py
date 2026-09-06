from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Index, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from typing import Optional

Base = declarative_base()


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    readings = relationship("WeatherReading", back_populates="station", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="station", cascade="all, delete-orphan")
    health_records = relationship("SensorHealth", back_populates="station", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Station {self.station_id}>"


class WeatherReading(Base):
    __tablename__ = "weather_readings"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(20), ForeignKey("stations.station_id"), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    temperature = Column(Float, nullable=False)
    pressure = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    is_anomalous = Column(Boolean, default=False, index=True)
    anomaly_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    station = relationship("Station", back_populates="readings")

    __table_args__ = (
        Index("ix_station_timestamp", "station_id", "timestamp"),
    )

    def __repr__(self):
        return f"<WeatherReading {self.station_id} {self.timestamp}>"


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(20), ForeignKey("stations.station_id"), index=True, nullable=False)
    reading_id = Column(Integer, ForeignKey("weather_readings.id"), nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    parameter = Column(String(20), nullable=False)  # temperature, pressure, humidity
    observed_value = Column(Float, nullable=False)
    expected_value = Column(Float, nullable=True)
    corrected_value = Column(Float, nullable=True)
    correction_confidence = Column(Float, default=0.0)

    anomaly_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False)  # NORMAL, LOW, SUSPICIOUS, HIGH, CRITICAL
    root_cause = Column(String(50), nullable=False)

    rule_score = Column(Float, default=0.0)
    isolation_forest_score = Column(Float, default=0.0)
    autoencoder_score = Column(Float, default=0.0)
    temporal_score = Column(Float, default=0.0)
    multivariate_score = Column(Float, default=0.0)
    spatial_score = Column(Float, default=0.0)

    explanation = Column(Text, nullable=True)
    contributing_factors = Column(Text, nullable=True)  # JSON string
    recommended_action = Column(Text, nullable=True)

    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    station = relationship("Station", back_populates="anomalies")

    def __repr__(self):
        return f"<Anomaly {self.station_id} {self.parameter} score={self.anomaly_score}>"


class SensorHealth(Base):
    __tablename__ = "sensor_health"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(20), ForeignKey("stations.station_id"), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)

    overall_health = Column(Float, nullable=False)
    temperature_health = Column(Float, nullable=False)
    pressure_health = Column(Float, default=100.0)
    humidity_health = Column(Float, nullable=False)

    status = Column(String(30), nullable=False)  # HEALTHY, WARNING, MAINTENANCE_RECOMMENDED, CRITICAL

    anomaly_count_24h = Column(Integer, default=0)
    drift_score = Column(Float, default=0.0)
    missing_data_ratio = Column(Float, default=0.0)
    frozen_count = Column(Integer, default=0)
    comm_failure_count = Column(Integer, default=0)
    avg_reconstruction_error = Column(Float, default=0.0)

    risk_level = Column(String(20), default="LOW")  # LOW, MEDIUM, HIGH
    maintenance_recommendation = Column(Text, nullable=True)
    days_until_maintenance = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    station = relationship("Station", back_populates="health_records")

    def __repr__(self):
        return f"<SensorHealth {self.station_id} overall={self.overall_health}>"


class AnomalyInjectionLog(Base):
    __tablename__ = "anomaly_injection_log"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(20), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    fault_type = Column(String(50), nullable=False)
    parameter = Column(String(20), nullable=False)
    original_value = Column(Float, nullable=False)
    injected_value = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AnomalyInjectionLog {self.station_id} {self.fault_type}>"


class ModelMetrics(Base):
    __tablename__ = "model_metrics"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(50), nullable=False)
    model_version = Column(String(20), nullable=False)
    evaluation_date = Column(DateTime, default=datetime.utcnow)

    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    false_positive_rate = Column(Float, nullable=True)
    false_negative_rate = Column(Float, nullable=True)
    detection_latency_ms = Column(Float, nullable=True)

    anomaly_type = Column(String(50), nullable=True)  # Per-type metrics
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ModelMetrics {self.model_name} v{self.model_version}>"