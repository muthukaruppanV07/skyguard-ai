"""Trained/evaluated model results registry."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class ModelResult(Base):
    __tablename__ = "app_model_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, default="f1")
    metric_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    details: Mapped[str] = mapped_column(String(2000), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
