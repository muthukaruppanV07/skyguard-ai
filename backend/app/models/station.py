"""Station registry (one row per AWS)."""

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class Station(Base):
    __tablename__ = "app_stations"

    # Required fields per spec
    station_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    # ACTIVE | MAINTENANCE | OFFLINE
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
