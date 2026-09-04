from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import Station, Reading, Anomaly, SensorHealth, Alert, ModelRun
from backend.models.anomaly import AnomalySeverity, RootCause
from backend.models.sensor_health import SensorType, HealthStatus
from backend.models.alert import AlertSeverity
from backend.models.model_run import ModelType


class StationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[Station]:
        result = await self.session.execute(select(Station).order_by(Station.id))
        return list(result.scalars().all())

    async def get_by_id(self, station_id: str) -> Optional[Station]:
        result = await self.session.execute(
            select(Station).where(Station.id == station_id)
        )
        return result.scalar_one_or_none()

    async def get_active(self) -> List[Station]:
        result = await self.session.execute(
            select(Station).where(Station.status == "ACTIVE")
        )
        return list(result.scalars().all())


class ReadingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, reading: Reading) -> Reading:
        self.session.add(reading)
        await self.session.flush()
        return reading

    async def get_latest(self, station_id: str) -> Optional[Reading]:
        result = await self.session.execute(
            select(Reading)
            .where(Reading.station_id == station_id)
            .order_by(desc(Reading.timestamp))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_all_stations(self) -> List[Reading]:
        subquery = (
            select(Reading.station_id, func.max(Reading.timestamp).label("max_ts"))
            .group_by(Reading.station_id)
            .subquery()
        )
        result = await self.session.execute(
            select(Reading)
            .join(
                subquery,
                and_(
                    Reading.station_id == subquery.c.station_id,
                    Reading.timestamp == subquery.c.max_ts,
                ),
            )
        )
        return list(result.scalars().all())

    async def get_by_station_time_range(
        self, station_id: str, start: datetime, end: datetime, limit: int = 1000
    ) -> List[Reading]:
        result = await self.session.execute(
            select(Reading)
            .where(
                and_(
                    Reading.station_id == station_id,
                    Reading.timestamp >= start,
                    Reading.timestamp <= end,
                )
            )
            .order_by(Reading.timestamp)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_for_features(
        self, station_id: str, minutes: int = 120, limit: int = 200
    ) -> List[Reading]:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        result = await self.session.execute(
            select(Reading)
            .where(
                and_(
                    Reading.station_id == station_id,
                    Reading.timestamp >= cutoff,
                )
            )
            .order_by(desc(Reading.timestamp))
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))


class AnomalyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, anomaly: Anomaly) -> Anomaly:
        self.session.add(anomaly)
        await self.session.flush()
        return anomaly

    async def get_by_id(self, anomaly_id: int) -> Optional[Anomaly]:
        result = await self.session.execute(
            select(Anomaly).where(Anomaly.id == anomaly_id)
        )
        return result.scalar_one_or_none()

    async def get_by_reading_id(self, reading_id: int) -> Optional[Anomaly]:
        result = await self.session.execute(
            select(Anomaly).where(Anomaly.reading_id == reading_id)
        )
        return result.scalar_one_or_none()

    async def get_recent(
        self,
        station_id: Optional[str] = None,
        severity: Optional[AnomalySeverity] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> List[Anomaly]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = select(Anomaly).where(Anomaly.timestamp >= cutoff)

        if station_id:
            query = query.where(Anomaly.station_id == station_id)
        if severity:
            query = query.where(Anomaly.severity == severity)

        query = query.order_by(desc(Anomaly.timestamp)).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        total = await self.session.execute(
            select(func.count(Anomaly.id)).where(Anomaly.timestamp >= cutoff)
        )
        by_severity = await self.session.execute(
            select(Anomaly.severity, func.count(Anomaly.id))
            .where(Anomaly.timestamp >= cutoff)
            .group_by(Anomaly.severity)
        )
        by_cause = await self.session.execute(
            select(Anomaly.root_cause, func.count(Anomaly.id))
            .where(Anomaly.timestamp >= cutoff)
            .group_by(Anomaly.root_cause)
        )
        avg_score = await self.session.execute(
            select(func.avg(Anomaly.anomaly_score)).where(Anomaly.timestamp >= cutoff)
        )

        return {
            "total": total.scalar() or 0,
            "by_severity": {s.value: c for s, c in by_severity.all()},
            "by_cause": {c.value: cnt for c, cnt in by_cause.all()},
            "avg_score": float(avg_score.scalar() or 0),
        }


class SensorHealthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, health: SensorHealth) -> SensorHealth:
        existing = await self.session.execute(
            select(SensorHealth).where(
                and_(
                    SensorHealth.station_id == health.station_id,
                    SensorHealth.sensor_type == health.sensor_type,
                )
            )
        )
        existing_health = existing.scalar_one_or_none()
        if existing_health:
            for key, value in health.__dict__.items():
                if not key.startswith("_"):
                    setattr(existing_health, key, value)
            return existing_health
        self.session.add(health)
        await self.session.flush()
        return health

    async def get_by_station(self, station_id: str) -> List[SensorHealth]:
        result = await self.session.execute(
            select(SensorHealth).where(SensorHealth.station_id == station_id)
        )
        return list(result.scalars().all())

    async def get_network_summary(self) -> Dict[str, Any]:
        result = await self.session.execute(
            select(
                SensorHealth.station_id,
                SensorHealth.sensor_type,
                SensorHealth.health_score,
                SensorHealth.status,
            )
        )
        data = result.all()

        summary = {"stations": {}, "overall_avg": 0.0}
        scores = []
        for station_id, sensor_type, score, status in data:
            if station_id not in summary["stations"]:
                summary["stations"][station_id] = {}
            summary["stations"][station_id][sensor_type.value] = {
                "score": score,
                "status": status.value,
            }
            scores.append(score)

        summary["overall_avg"] = sum(scores) / len(scores) if scores else 0.0
        return summary


class AlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, alert: Alert) -> Alert:
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def get_unacknowledged(self, limit: int = 50) -> List[Alert]:
        result = await self.session.execute(
            select(Alert)
            .where(Alert.acknowledged == False)
            .order_by(desc(Alert.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def acknowledge(self, alert_id: int) -> Optional[Alert]:
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if alert:
            alert.acknowledged = True
            alert.acknowledged_at = datetime.utcnow()
        return alert


class ModelRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, model_run: ModelRun) -> ModelRun:
        self.session.add(model_run)
        await self.session.flush()
        return model_run

    async def get_latest(self, model_name: ModelType) -> Optional[ModelRun]:
        result = await self.session.execute(
            select(ModelRun)
            .where(ModelRun.model_name == model_name)
            .order_by(desc(ModelRun.trained_at))
            .limit(1)
        )
        return result.scalar_one_or_none()