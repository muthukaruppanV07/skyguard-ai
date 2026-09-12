"""Maintenance recommendations for field technicians."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class MaintenanceRecommendation(Base):
    __tablename__ = "app_maintenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("app_stations.station_id"), nullable=False, index=True
    )
    # LOW | MEDIUM | HIGH | URGENT
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # OPEN | ACKNOWLEDGED | RESOLVED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
