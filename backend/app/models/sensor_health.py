"""Per-station, per-sensor health (0-100)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class SensorHealth(Base):
    __tablename__ = "app_sensor_health"
    __table_args__ = (UniqueConstraint("station_id", "sensor_type", name="uq_health_station_sensor"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("app_stations.station_id"), nullable=False, index=True
    )
    # TEMPERATURE | PRESSURE | HUMIDITY
    sensor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    # HEALTHY | WARNING | CRITICAL
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="HEALTHY")
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
