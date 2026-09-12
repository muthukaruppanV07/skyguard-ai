"""Raw AWS observations (T/P/H core inputs). Raw data is never overwritten."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class Observation(Base):
    __tablename__ = "app_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("app_stations.station_id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    pressure: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
