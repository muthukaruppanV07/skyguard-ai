"""Persisted report runs (generated snapshots)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class ReportRun(Base):
    __tablename__ = "app_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    params: Mapped[str] = mapped_column(String(1000), nullable=False, default="{}")
    payload: Mapped[str] = mapped_column(String(60000), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
