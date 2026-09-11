"""Async SQLite session + Base + init/seed helpers."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DATABASE_ECHO, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    # Import models so metadata is registered before create_all
    from backend.app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_columns)


def _ensure_columns(conn) -> None:
    """Additive SQLite migration for dev DBs created before new columns existed."""
    import sqlalchemy as sa

    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if "app_anomalies" in tables:
        existing = {c["name"] for c in inspector.get_columns("app_anomalies")}
        for name, ddl in (
            ("anomaly_type", "VARCHAR(40) DEFAULT 'NORMAL'"),
            ("detector_results", "VARCHAR(4000) DEFAULT '{}'"),
            ("evidence", "VARCHAR(4000) DEFAULT '{}'"),
            ("resolved", "BOOLEAN DEFAULT 0"),
        ):
            if name not in existing:
                conn.execute(sa.text(f"ALTER TABLE app_anomalies ADD COLUMN {name} {ddl}"))
    if "app_alerts" in tables:
        existing = {c["name"] for c in inspector.get_columns("app_alerts")}
        if "muted" not in existing:
            conn.execute(sa.text("ALTER TABLE app_alerts ADD COLUMN muted BOOLEAN DEFAULT 0"))


async def seed_stations() -> int:
    """Insert the 8 default AWS stations if missing. Returns count created."""
    from sqlalchemy import select

    from backend.app.models.station import Station

    created = 0
    async with AsyncSessionLocal() as session:
        for s in settings.STATION_COORDS:
            existing = await session.get(Station, s["station_id"])
            if existing is None:
                session.add(
                    Station(
                        station_id=s["station_id"],
                        name=s["name"],
                        latitude=s["latitude"],
                        longitude=s["longitude"],
                        status="ACTIVE",
                    )
                )
                created += 1
        # Pseudo-station owning system-wide alerts (excluded from physical enumerations)
        if await session.get(Station, "SYSTEM") is None:
            session.add(Station(station_id="SYSTEM", name="Command Center",
                                latitude=20.0, longitude=78.0, status="ACTIVE"))
            created += 1
        await session.commit()
    return created


async def close_db() -> None:
    await engine.dispose()
