"""Operator alerts raised from anomalies."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class Alert(Base):
    __tablename__ = "app_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("app_stations.station_id"), nullable=False, index=True
    )
    anomaly_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("app_anomalies.id"), nullable=True, unique=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Operator-muted alerts stay stored but leave notification feeds
    muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
