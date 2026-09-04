import asyncio
from backend.database.session import init_db
from backend.config import settings
from backend.database.session import AsyncSessionLocal
from backend.models import Station, SensorHealth
from sqlalchemy import select
from backend.models.sensor_health import SensorType, HealthStatus
from backend.models.station import StationStatus


async def seed_stations() -> None:
    async with AsyncSessionLocal() as session:
        for station_config in settings.STATION_COORDS:
            existing = await session.execute(
                select(Station).where(Station.id == station_config["station_id"])
            )
            if existing.scalar_one_or_none():
                continue

            station = Station(
                id=station_config["station_id"],
                name=station_config["name"],
                latitude=station_config["latitude"],
                longitude=station_config["longitude"],
                elevation=station_config["elevation"],
                status=StationStatus.ACTIVE,
            )
            session.add(station)

            for sensor_type in SensorType:
                health = SensorHealth(
                    station_id=station_config["station_id"],
                    sensor_type=sensor_type,
                    health_score=100.0,
                    anomaly_count_24h=0,
                    anomaly_count_7d=0,
                    drift_detected=False,
                    frozen_count=0,
                    missing_count=0,
                    comm_failure_count=0,
                    reconstruction_error_avg=0.0,
                    status=HealthStatus.HEALTHY,
                )
                session.add(health)

        await session.commit()
        print(f"Seeded {len(settings.STATION_COORDS)} stations with sensor health records.")


async def main() -> None:
    print("Initializing database...")
    await init_db()
    print("Database tables created.")
    await seed_stations()
    print("Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(main())