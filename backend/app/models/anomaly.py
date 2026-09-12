"""Detected anomalies linked to observations."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class Anomaly(Base):
    __tablename__ = "app_anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("app_stations.station_id"), nullable=False, index=True
    )
    observation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("app_observations.id"), nullable=True, unique=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Unified 0-100 score + severity band
    score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="SUSPICIOUS")
    root_cause: Mapped[str] = mapped_column(String(50), nullable=False, default="SPIKE")
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Hybrid engine fields: type + full signal trail (JSON strings)
    anomaly_type: Mapped[str] = mapped_column(String(40), nullable=False, default="NORMAL")
    detector_results: Mapped[str] = mapped_column(String(4000), nullable=False, default="{}")
    evidence: Mapped[str] = mapped_column(String(4000), nullable=False, default="{}")
    # Operator workflow
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
