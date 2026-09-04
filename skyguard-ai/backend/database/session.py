from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from backend.config import settings
from backend.database.models import Base

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in settings.DATABASE_URL else None,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _seed_stations()


def _seed_stations():
    from backend.database.models import Station
    from backend.config import settings

    db = SessionLocal()
    try:
        for station_id in settings.STATION_IDS:
            existing = db.query(Station).filter(Station.station_id == station_id).first()
            if not existing:
                lat, lon = settings.STATION_COORDINATES.get(station_id, (28.6139, 77.2090))
                station = Station(
                    station_id=station_id,
                    name=f"Automatic Weather Station {station_id}",
                    latitude=lat,
                    longitude=lon,
                    elevation=200.0,
                    is_active=True,
                )
                db.add(station)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error seeding stations: {e}")
    finally:
        db.close()


def drop_db():
    Base.metadata.drop_all(bind=engine)