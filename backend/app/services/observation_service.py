"""Foundation detection: deterministic range QC -> anomaly + alert + health.

ML (IsolationForest / autoencoder) plugs in later under backend/app/ml/.
This keeps POST /observations useful from day one without heavy deps.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.alert import Alert
from backend.app.models.anomaly import Anomaly
from backend.app.models.maintenance import MaintenanceRecommendation
from backend.app.models.observation import Observation
from backend.app.models.station import Station
from backend.app.schemas.schemas import ObservationIn


def _severity_for(score: float) -> str:
    if score >= settings.ANOMALY_THRESHOLD_CRITICAL:
        return "CRITICAL"
    if score >= settings.ANOMALY_THRESHOLD_HIGH:
        return "HIGH"
    if score >= settings.ANOMALY_THRESHOLD_SUSPICIOUS:
        return "SUSPICIOUS"
    if score >= 30:
        return "LOW"
    return "NORMAL"


def rule_score(obs: ObservationIn) -> tuple[float, str, str]:
    """Score 0-100 from range violations. Returns (score, root_cause, message)."""
    violations: list[str] = []
    if not settings.TEMP_MIN <= obs.temperature <= settings.TEMP_MAX:
        violations.append(f"temperature {obs.temperature}C outside [{settings.TEMP_MIN},{settings.TEMP_MAX}]")
    if not settings.PRESSURE_MIN <= obs.pressure <= settings.PRESSURE_MAX:
        violations.append(f"pressure {obs.pressure}hPa outside [{settings.PRESSURE_MIN},{settings.PRESSURE_MAX}]")
    if not settings.HUMIDITY_MIN <= obs.humidity <= settings.HUMIDITY_MAX:
        violations.append(f"humidity {obs.humidity}% outside [{settings.HUMIDITY_MIN},{settings.HUMIDITY_MAX}]")
    if violations:
        return 95.0, "INVALID_DATA", "; ".join(violations)
    # Near-boundary values are suspicious (sensor drift early warning)
    margins: list[str] = []
    temp_span = settings.TEMP_MAX - settings.TEMP_MIN
    if abs(obs.temperature - settings.TEMP_MAX) < 0.05 * temp_span or abs(obs.temperature - settings.TEMP_MIN) < 0.05 * temp_span:
        margins.append("temperature near physical limit")
    if margins:
        return 55.0, "DRIFT", "; ".join(margins)
    return 5.0, "NORMAL", "within physical ranges"


async def _touch_sensor_health(session: AsyncSession, station_id: str, is_anomaly: bool) -> None:
    """Recompute health from actual trailing history (replaces blind deltas)."""
    from backend.app.health.engine import recompute_and_store

    await recompute_and_store(session, station_id)


async def create_observation(session: AsyncSession, payload: ObservationIn) -> tuple[Observation, Anomaly | None]:
    station = await session.get(Station, payload.station_id)
    if station is None:
        raise ValueError(f"Unknown station_id: {payload.station_id}")

    obs = Observation(
        station_id=payload.station_id,
        timestamp=payload.timestamp,
        temperature=payload.temperature,
        pressure=payload.pressure,
        humidity=payload.humidity,
    )
    session.add(obs)
    await session.flush()  # assigns obs.id

    score, root_cause, message = rule_score(payload)
    anomaly: Anomaly | None = None
    if score >= settings.ANOMALY_THRESHOLD_SUSPICIOUS:
        severity = _severity_for(score)
        anomaly = Anomaly(
            station_id=payload.station_id,
            observation_id=obs.id,
            timestamp=payload.timestamp,
            score=score,
            severity=severity,
            root_cause=root_cause,
            message=message,
            confidence=0.9 if root_cause == "INVALID_DATA" else 0.6,
        )
        session.add(anomaly)
        await session.flush()
        session.add(
            Alert(
                station_id=payload.station_id,
                anomaly_id=anomaly.id,
                severity=severity,
                message=f"{payload.station_id}: {message}",
            )
        )
        if severity in ("HIGH", "CRITICAL"):
            session.add(
                MaintenanceRecommendation(
                    station_id=payload.station_id,
                    priority="URGENT" if severity == "CRITICAL" else "HIGH",
                    recommendation=f"Inspect sensors at {payload.station_id}",
                    reason=message,
                )
            )

    await _touch_sensor_health(session, payload.station_id, anomaly is not None)
    await session.commit()
    await session.refresh(obs)
    if anomaly is not None:
        await session.refresh(anomaly)
    return obs, anomaly


async def observation_count(session: AsyncSession, station_id: str | None = None) -> int:
    stmt = select(func.count(Observation.id))
    if station_id:
        stmt = stmt.where(Observation.station_id == station_id)
    return (await session.execute(stmt)).scalar_one()
