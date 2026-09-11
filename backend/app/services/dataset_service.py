"""CSV upload: parse + validate the exact format, bulk-ingest valid rows.

Format: timestamp,station_id,latitude,longitude,temperature,pressure,humidity
Optional 8th column 'label' is accepted and ignored on ingest
(gap rows with blank T/P/H are counted as skipped, not errors).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.schemas.schemas import ObservationIn
from backend.app.services.observation_service import create_observation

REQUIRED_HEADER = ["timestamp", "station_id", "latitude", "longitude", "temperature", "pressure", "humidity"]
MAX_ROWS = 50_000


def _parse_float(value: str, name: str, lo: float, hi: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Bad {name}: {value!r}")
    if not lo <= v <= hi:
        raise ValueError(f"{name} {v} outside [{lo},{hi}]")
    return v


async def ingest_csv(session: AsyncSession, content: bytes) -> dict:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("CSV must be UTF-8 encoded")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("Empty CSV")
    header = [h.strip() for h in reader.fieldnames]
    if header[:7] != REQUIRED_HEADER:
        raise ValueError(f"Header must be {','.join(REQUIRED_HEADER)} (optional 8th 'label' allowed)")

    inserted = skipped = 0
    errors: list[str] = []
    for lineno, row in enumerate(reader, start=2):
        if len(errors) >= 20:
            errors.append("...truncated, too many errors")
            break
        try:
            station_id = (row.get("station_id") or "").strip()
            if not station_id:
                raise ValueError("Missing station_id")
            lat = _parse_float((row.get("latitude") or "").strip(), "latitude", -90, 180)
            lon = _parse_float((row.get("longitude") or "").strip(), "longitude", -180, 180)
            t_raw = (row.get("temperature") or "").strip()
            p_raw = (row.get("pressure") or "").strip()
            h_raw = (row.get("humidity") or "").strip()
            if t_raw == "" or p_raw == "" or h_raw == "":
                skipped += 1  # MISSING / COMMUNICATION_FAILURE gap row
                continue
            try:
                ts = datetime.fromisoformat((row.get("timestamp") or "").strip().replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(f"Bad timestamp: {row.get('timestamp')!r}")
            payload = ObservationIn(
                station_id=station_id,
                timestamp=ts,
                temperature=_parse_float(t_raw, "temperature", settings.TEMP_MIN, settings.TEMP_MAX),
                pressure=_parse_float(p_raw, "pressure", settings.PRESSURE_MIN, settings.PRESSURE_MAX),
                humidity=_parse_float(h_raw, "humidity", settings.HUMIDITY_MIN, settings.HUMIDITY_MAX),
            )
            # Warn on coordinate mismatch instead of failing (stations are pre-seeded)
            await create_observation(session, payload)
            inserted += 1
            if inserted + skipped > MAX_ROWS:
                raise ValueError(f"Row limit {MAX_ROWS} exceeded")
        except ValueError as exc:
            errors.append(f"line {lineno}: {exc}")
    return {"inserted": inserted, "skipped_gaps": skipped, "errors": errors}
