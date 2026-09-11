"""Realistic synthetic AWS dataset generator (SIH 26073).

Physics (no external data needed):
- Diurnal temperature cycle (peak ~14:00, trough ~04:30)
- Seasonal cycle (North-India summer peak ~mid-May)
- Station climates: coastal humid vs inland dry vs high-altitude low pressure
- Pressure: elevation-corrected base, semi-diurnal tide, inverse coupling to T
- Humidity: inverse coupling to T + diurnal + station base
- Gaussian natural fluctuations + bounded random-walk synoptic drift
- All values clamped to IMD plausibility ranges from core config

Labels: NORMAL, SPIKE, DROP, FROZEN, DRIFT, MISSING,
COMMUNICATION_FAILURE, MULTIVARIATE_ANOMALY, SENSOR_FAULT, WEATHER_EVENT

Stdlib only (random/math/csv/datetime) so the script runs anywhere.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

LABELS = [
    "NORMAL",
    "SPIKE",
    "DROP",
    "FROZEN",
    "DRIFT",
    "MISSING",
    "COMMUNICATION_FAILURE",
    "MULTIVARIATE_ANOMALY",
    "SENSOR_FAULT",
    "WEATHER_EVENT",
]

CSV_HEADER = ["timestamp", "station_id", "latitude", "longitude", "temperature", "pressure", "humidity"]
CSV_HEADER_LABELLED = CSV_HEADER + ["label"]

# Per-station climate: base temp/humidity, seasonal + diurnal amplitudes,
# sea-level pressure reference + elevation for realistic station pressure.
# Elevation: Delhi 216, Mumbai 14, Bangalore 920, Chennai 6.7, Kolkata 9,
# Hyderabad 505, Pune 560, Ahmedabad 53.
STATION_CLIMATE = {
    "AWS001": {"base_temp": 25.0, "base_hum": 55.0, "season_amp": 7.0, "diurnal_amp": 5.5, "elev_m": 216.0},
    "AWS002": {"base_temp": 27.5, "base_hum": 74.0, "season_amp": 2.5, "diurnal_amp": 3.5, "elev_m": 14.0},
    "AWS003": {"base_temp": 23.5, "base_hum": 60.0, "season_amp": 3.5, "diurnal_amp": 5.0, "elev_m": 920.0},
    "AWS004": {"base_temp": 28.5, "base_hum": 70.0, "season_amp": 3.0, "diurnal_amp": 3.8, "elev_m": 6.7},
    "AWS005": {"base_temp": 27.0, "base_hum": 72.0, "season_amp": 4.5, "diurnal_amp": 4.2, "elev_m": 9.0},
    "AWS006": {"base_temp": 26.0, "base_hum": 55.0, "season_amp": 5.0, "diurnal_amp": 5.2, "elev_m": 505.0},
    "AWS007": {"base_temp": 24.0, "base_hum": 58.0, "season_amp": 5.0, "diurnal_amp": 5.0, "elev_m": 560.0},
    "AWS008": {"base_temp": 27.0, "base_hum": 45.0, "season_amp": 6.0, "diurnal_amp": 6.0, "elev_m": 53.0},
}

SEA_LEVEL_PRESSURE = 1013.25
LAPSE_HPA_PER_M = 0.12  # ~12 hPa per 100 m


@dataclass
class GeneratorConfig:
    num_stations: int = 4
    num_observations: int = 1000  # total rows across all stations
    sampling_interval_minutes: int = 60
    anomaly_percentage: float = 5.0  # % of rows with non-NORMAL label
    seed: int = 42
    start: datetime = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))


@dataclass
class ObsRow:
    timestamp: datetime
    station_id: str
    latitude: float
    longitude: float
    temperature: float | None  # None -> MISSING / COMMUNICATION_FAILURE gap row
    pressure: float | None
    humidity: float | None
    label: str = "NORMAL"


def _station_pressure_base(elev_m: float) -> float:
    return SEA_LEVEL_PRESSURE - LAPSE_HPA_PER_M * elev_m


def _clean_physics(climate: dict, ts: datetime, rng: random.Random, state: dict) -> tuple[float, float, float]:
    """Realistic T/P/H for one timestamp. state holds slow synoptic random-walk."""
    hour = ts.hour + ts.minute / 60.0
    doy = ts.timetuple().tm_yday
    # Diurnal: min ~04:30, max ~14:00
    diurnal = math.sin(2 * math.pi * (hour - 8.0) / 24.0)
    # Seasonal: peak mid-May (doy ~135)
    seasonal = math.sin(2 * math.pi * (doy - 135.0 + 91.0) / 365.0)
    temp = (
        climate["base_temp"]
        + climate["season_amp"] * seasonal
        + climate["diurnal_amp"] * diurnal
        + rng.gauss(0, 0.4)
    )
    # Slow synoptic drift (bounded random walk, shared per station)
    state["synoptic"] = max(-3.0, min(3.0, state.get("synoptic", 0.0) + rng.gauss(0, 0.15)))
    temp += state["synoptic"] * 0.5
    # Pressure: elevation base, semi-diurnal atmospheric tide, inverse T coupling
    tide = 0.8 * math.sin(2 * math.pi * hour / 12.0)
    pressure = (
        _station_pressure_base(climate["elev_m"])
        - 0.15 * (temp - climate["base_temp"])
        + tide
        + state["synoptic"] * 0.8
        + rng.gauss(0, 0.3)
    )
    # Humidity: inverse T coupling + weak diurnal, station base
    humidity = (
        climate["base_hum"]
        - 1.8 * (temp - climate["base_temp"])
        - 2.0 * diurnal
        + rng.gauss(0, 1.5)
    )
    return round(max(-10.0, min(50.0, temp)), 2), round(max(850.0, min(1100.0, pressure)), 2), round(
        max(0.0, min(100.0, humidity)), 2
    )


def _inject_fault(rows: list[ObsRow], rng: random.Random) -> str:
    """Apply one fault episode to random contiguous segment. Returns label used."""
    fault = rng.choices(
        ["SPIKE", "DROP", "FROZEN", "DRIFT", "MULTIVARIATE_ANOMALY", "SENSOR_FAULT", "WEATHER_EVENT"],
        weights=[20, 15, 15, 12, 12, 13, 13],
        k=1,
    )[0]
    n = len(rows)
    if n < 3:
        return "NORMAL"
    if fault in ("SPIKE", "DROP"):
        i = rng.randrange(n)
        r = rows[i]
        if r.temperature is None:
            return "NORMAL"
        delta = rng.uniform(8, 15)
        target = rng.choice(["t", "p", "h"])
        if target == "t":
            r.temperature = round(min(50.0, max(-10.0, r.temperature + (delta if fault == "SPIKE" else -delta))), 2)
        elif target == "p":
            r.pressure = round(min(1100.0, max(850.0, r.pressure + (delta if fault == "SPIKE" else -delta))), 2)
        else:
            r.humidity = round(min(100.0, max(0.0, r.humidity + (delta * 2 if fault == "SPIKE" else -delta * 2))), 2)
        r.label = fault
    elif fault == "FROZEN":
        i = rng.randrange(max(1, n - 12))
        length = rng.randint(6, min(24, n - i))
        t0, p0, h0 = rows[i].temperature, rows[i].pressure, rows[i].humidity
        for r in rows[i : i + length]:
            r.temperature, r.pressure, r.humidity, r.label = t0, p0, h0, "FROZEN"
    elif fault == "DRIFT":
        i = rng.randrange(max(1, n - 16))
        length = rng.randint(12, min(48, n - i))
        slope = rng.uniform(0.3, 0.8) * rng.choice([1, -1])
        for k, r in enumerate(rows[i : i + length]):
            if r.temperature is not None:
                r.temperature = round(max(-10.0, min(50.0, r.temperature + slope * k * 0.3)), 2)
                r.label = "DRIFT"
    elif fault == "MULTIVARIATE_ANOMALY":
        i = rng.randrange(n)
        r = rows[i]
        if r.temperature is None:
            return "NORMAL"
        # Physically inconsistent: hot AND saturated (real heat -> humidity drops)
        r.temperature = round(min(50.0, r.temperature + rng.uniform(4, 8)), 2)
        r.humidity = round(min(100.0, (r.humidity or 50) + rng.uniform(20, 30)), 2)
        r.label = "MULTIVARIATE_ANOMALY"
    elif fault == "SENSOR_FAULT":
        i = rng.randrange(max(1, n - 10))
        length = rng.randint(6, min(18, n - i))
        bias = rng.uniform(5, 10) * rng.choice([1, -1])
        for r in rows[i : i + length]:
            if r.temperature is not None:
                r.temperature = round(max(-10.0, min(50.0, r.temperature + bias)), 2)
                r.label = "SENSOR_FAULT"
    elif fault == "WEATHER_EVENT":
        # Genuine event: coherent heat spike + humidity drop + pressure dip over hours
        i = rng.randrange(max(1, n - 30))
        length = rng.randint(12, min(36, n - i))
        for r in rows[i : i + length]:
            if r.temperature is not None:
                r.temperature = round(min(50.0, r.temperature + rng.uniform(3, 5)), 2)
                r.humidity = round(max(0.0, (r.humidity or 50) - rng.uniform(8, 15)), 2)
                r.pressure = round(max(850.0, (r.pressure or 1000) - rng.uniform(2, 5)), 2)
                r.label = "WEATHER_EVENT"
    return fault


def generate_dataset(cfg: GeneratorConfig, station_table: list[dict]) -> list[ObsRow]:
    """Generate labelled rows. station_table: [{station_id, latitude, longitude}]."""
    if cfg.num_stations < 1 or cfg.num_observations < 1:
        raise ValueError("num_stations and num_observations must be >= 1")
    if not 0 <= cfg.anomaly_percentage <= 100:
        raise ValueError("anomaly_percentage must be 0-100")
    if cfg.sampling_interval_minutes < 1:
        raise ValueError("sampling_interval_minutes must be >= 1")
    stations = station_table[: cfg.num_stations]
    if len(stations) < cfg.num_stations:
        raise ValueError(f"Only {len(stations)} stations available, requested {cfg.num_stations}")

    rng = random.Random(cfg.seed)
    per_station = max(1, cfg.num_observations // cfg.num_stations)
    all_rows: list[ObsRow] = []
    for s in stations:
        climate = STATION_CLIMATE.get(
            s["station_id"],
            {"base_temp": 26.0, "base_hum": 60.0, "season_amp": 4.0, "diurnal_amp": 4.5, "elev_m": 200.0},
        )
        state: dict = {"synoptic": 0.0}
        ts = cfg.start
        for _ in range(per_station):
            t, p, h = _clean_physics(climate, ts, rng, state)
            all_rows.append(
                ObsRow(
                    timestamp=ts,
                    station_id=s["station_id"],
                    latitude=s["latitude"],
                    longitude=s["longitude"],
                    temperature=t,
                    pressure=p,
                    humidity=h,
                )
            )
            ts += timedelta(minutes=cfg.sampling_interval_minutes)

    # Inject point/segment faults to reach target anomaly share
    target = int(len(all_rows) * cfg.anomaly_percentage / 100.0)
    # Group rows per station so FROZEN/DRIFT segments stay contiguous
    by_station: dict[str, list[ObsRow]] = {}
    for r in all_rows:
        by_station.setdefault(r.station_id, []).append(r)
    # Gap faults get a reserved quota so MISSING / COMMUNICATION_FAILURE
    # always appear in labelled eval sets (fault episodes alone may fill budget).
    gap_quota = min(len(all_rows) // 2, max(2 if target else 0, int(target * 0.25)))
    fault_target = max(0, target - gap_quota)
    anomalous = 0
    guard = 0
    while anomalous < fault_target and guard < target * 5 + 50:
        guard += 1
        sid = rng.choice(list(by_station.keys()))
        _inject_fault(by_station[sid], rng)
        anomalous = sum(1 for r in all_rows if r.label != "NORMAL")

    # Gap faults: blank out NORMAL rows for MISSING / COMMUNICATION_FAILURE
    normal_rows = [r for r in all_rows if r.label == "NORMAL"]
    gap_rows = rng.sample(normal_rows, min(gap_quota, len(normal_rows)))
    for i, r in enumerate(gap_rows):
        r.temperature, r.pressure, r.humidity = None, None, None
        r.label = "COMMUNICATION_FAILURE" if i % 3 == 0 else "MISSING"

    all_rows.sort(key=lambda r: (r.timestamp, r.station_id))
    return all_rows


def rows_to_dicts(rows: list[ObsRow], labelled: bool = True) -> list[dict]:
    out = []
    for r in rows:
        d = {
            "timestamp": r.timestamp.isoformat(),
            "station_id": r.station_id,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "temperature": "" if r.temperature is None else r.temperature,
            "pressure": "" if r.pressure is None else r.pressure,
            "humidity": "" if r.humidity is None else r.humidity,
        }
        if labelled:
            d["label"] = r.label
        out.append(d)
    return out


def label_histogram(rows: list[ObsRow]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for r in rows:
        hist[r.label] = hist.get(r.label, 0) + 1
    return hist
