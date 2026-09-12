"""Baseline seeding tests: empty DB gets history, live DB untouched."""

import asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.database.session import Base
from backend.app.models.observation import Observation
from backend.app.models.station import Station
from backend.app.simulation.engine import seed_baseline_history

STATIONS = [{"station_id": f"S{i}", "latitude": 28.0, "longitude": 77.0} for i in range(1, 4)]


def run(coro):
    return asyncio.run(coro)


async def seed_db_coro():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return eng, async_sessionmaker(eng, expire_on_commit=False)


def test_seeds_empty_db_only():
    async def _run():
        eng, Session = await seed_db_coro()
        async with Session() as s:
            for st in STATIONS:
                s.add(Station(station_id=st["station_id"], name=st["station_id"],
                              latitude=st["latitude"], longitude=st["longitude"], status="ACTIVE"))
            await s.commit()
            n = await seed_baseline_history(Session, STATIONS, hours=48)
            assert n == 3 * 48
            total = (await s.execute(select(func.count()).select_from(Observation))).scalar_one()
            assert total == 144
            # second call is a no-op on live data
            assert await seed_baseline_history(Session, STATIONS, hours=48) == 0
            # sane physics ranges on seeded rows
            row = (await s.execute(select(Observation).limit(1))).scalars().one()
            assert -10 <= row.temperature <= 50
            assert 850 <= row.pressure <= 1100
            assert 0 <= row.humidity <= 100
        await eng.dispose()

    run(_run())
