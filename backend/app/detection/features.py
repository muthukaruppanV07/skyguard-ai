"""Reusable T/P/H feature engineering (SIH 26073).

Inputs: chronologically sorted rows, each
  {"timestamp": datetime, "temperature": float|None,
   "pressure": float|None, "humidity": float|None}
Only core AWS parameters are used — no external data.

Rolling statistics are computed over the *previous* `window` values
(excluding the current row) so deviation features measure surprise
against history without leakage. At least MIN_PERIODS (3) valid values
are required, otherwise the feature is None.

Missing values (None or NaN) never raise: every derived feature is
None when its inputs are unavailable.

Output per row (see FEATURE_NAMES):
- per-sensor: {s}_prev/change/rate/rolling_mean/median/std/mad/deviation/
  historical_deviation/identical_streak/missing_streak/sudden_change/drift
  plus spec aliases temperature_rolling_mean/std/deviation, pressure_trend, ...
- time: hour/day/month/day_of_year/season_sin/season_cos
- multivariate: th/tp/hp relationships, rolling correlations, distance
- aggregate: missing_value_streak, sudden_change, drift_indicator
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone

SENSORS = ("temperature", "pressure", "humidity")
MIN_PERIODS = 3

# Step-change thresholds for sudden_change flags (per sampling step)
SUDDEN_THRESHOLDS = {"temperature": 3.0, "pressure": 3.0, "humidity": 10.0}

TIME_FEATURES = ("hour", "day", "month", "day_of_year", "season_sin", "season_cos")

_PER_SENSOR_SUFFIXES = (
    "prev",
    "change",
    "rate",
    "rolling_mean",
    "rolling_median",
    "rolling_std",
    "rolling_mad",
    "deviation",
    "historical_deviation",
    "identical_streak",
    "missing_streak",
    "sudden_change",
    "drift",
)

FEATURE_NAMES: list[str] = []
for _s in SENSORS:
    FEATURE_NAMES.extend(f"{_s}_{sfx}" for sfx in _PER_SENSOR_SUFFIXES)
FEATURE_NAMES.extend(
    [
        "pressure_trend",  # alias of pressure_drift (spec name)
        "temperature_humidity_relationship",
        "temperature_pressure_relationship",
        "humidity_pressure_relationship",
        "rolling_corr_th",
        "rolling_corr_tp",
        "rolling_corr_hp",
        "multivariate_distance",
        "missing_value_streak",
        "sudden_change",
        "drift_indicator",
        *TIME_FEATURES,
    ]
)


def _is_missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if not _is_missing(x)]
    if len(xs) < MIN_PERIODS:
        return None
    return statistics.fmean(xs)


def _median(xs: list[float]) -> float | None:
    xs = [x for x in xs if not _is_missing(x)]
    if len(xs) < MIN_PERIODS:
        return None
    return statistics.median(xs)


def _std(xs: list[float]) -> float | None:
    xs = [x for x in xs if not _is_missing(x)]
    if len(xs) < MIN_PERIODS:
        return None
    if len(set(xs)) == 1:
        return 0.0
    return statistics.pstdev(xs)


def _mad(xs: list[float]) -> float | None:
    xs = [x for x in xs if not _is_missing(x)]
    if len(xs) < MIN_PERIODS:
        return None
    med = statistics.median(xs)
    return statistics.median([abs(x - med) for x in xs])


def _slope(xs: list[float | None]) -> float | None:
    """Least-squares slope per step over valid values (None if <3 valid)."""
    pts = [(i, x) for i, x in enumerate(xs) if not _is_missing(x)]
    if len(pts) < MIN_PERIODS:
        return None
    n = len(pts)
    sx = sum(i for i, _ in pts)
    sy = sum(v for _, v in pts)
    sxx = sum(i * i for i, _ in pts)
    sxy = sum(i * v for i, v in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


def _pearson(xs: list[float | None], ys: list[float | None]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if not _is_missing(x) and not _is_missing(y)]
    if len(pairs) < MIN_PERIODS:
        return None
    xa = [x for x, _ in pairs]
    ya = [y for _, y in pairs]
    if len(set(xa)) == 1 or len(set(ya)) == 1:
        return None
    mx, my = statistics.fmean(xa), statistics.fmean(ya)
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    vx = sum((x - mx) ** 2 for x in xa)
    vy = sum((y - my) ** 2 for y in ya)
    if vx <= 0 or vy <= 0:
        return None
    return cov / math.sqrt(vx * vy)


def _deviation(value: float | None, mean: float | None, std: float | None) -> float | None:
    if _is_missing(value) or mean is None or std is None:
        return None
    if std == 0:
        return 0.0 if value == mean else None
    return (value - mean) / std


def _time_features(ts: datetime) -> dict:
    doy = ts.timetuple().tm_yday
    return {
        "hour": ts.hour + ts.minute / 60.0,
        "day": ts.day,
        "month": ts.month,
        "day_of_year": doy,
        "season_sin": math.sin(2 * math.pi * doy / 365.0),
        "season_cos": math.cos(2 * math.pi * doy / 365.0),
    }


def compute_features(
    rows: list[dict],
    window: int = 6,
    drift_window: int = 24,
) -> list[dict]:
    """Compute the full feature vector for every input row.

    Args:
        rows: oldest-first dicts with timestamp/temperature/pressure/humidity.
        window: rolling window size for mean/median/std/mad/correlation.
        drift_window: window size for per-sensor drift slope.
    """
    if window < MIN_PERIODS:
        raise ValueError(f"window must be >= {MIN_PERIODS}")
    for i, r in enumerate(rows):
        if not isinstance(r.get("timestamp"), datetime):
            raise ValueError(f"row {i} is missing a datetime 'timestamp'")

    series = {s: [r.get(s) for r in rows] for s in SENSORS}
    # SQLite round-trips drop tzinfo; treat naive stamps as UTC so mixed
    # history (naive, from DB) + live rows (aware) never crash arithmetic.
    stamps: list[datetime] = [
        r["timestamp"] if r["timestamp"].tzinfo is not None else r["timestamp"].replace(tzinfo=timezone.utc)
        for r in rows
    ]
    out: list[dict] = []

    for i, r in enumerate(rows):
        f: dict = {}
        dt_min: float | None = None
        if i > 0:
            dt_min = (stamps[i] - stamps[i - 1]).total_seconds() / 60.0
            if dt_min is None or dt_min <= 0 or math.isnan(dt_min):
                dt_min = None

        sudden_any = 0
        missing_any_streak = 0
        drift_max = 0.0
        drift_max_valid = False
        z: dict[str, float | None] = {}

        for s in SENSORS:
            v = series[s][i]
            prev = series[s][i - 1] if i > 0 else None
            prev = None if _is_missing(prev) else prev
            change = None if (_is_missing(v) or prev is None) else v - prev
            rate = None if (change is None or dt_min is None) else change / dt_min

            hist = series[s][max(0, i - window) : i]
            rmean, rmed = _mean(hist), _median(hist)
            rstd, rmad = _std(hist), _mad(hist)
            dev = _deviation(v, rmean, rstd)

            full_hist = series[s][:i]
            hmean, hstd = _mean(full_hist), _std(full_hist)
            hdev = _deviation(v, hmean, hstd)

            # Consecutive identical values ending here (missing breaks the run)
            streak = 0
            if not _is_missing(v):
                j = i
                while j >= 0 and not _is_missing(series[s][j]) and series[s][j] == v:
                    streak += 1
                    j -= 1
            # Consecutive missing values ending here
            mstreak = 0
            j = i
            while j >= 0 and _is_missing(series[s][j]):
                mstreak += 1
                j -= 1

            sudden = 0
            if change is not None and abs(change) > SUDDEN_THRESHOLDS[s]:
                sudden = 1
                sudden_any = 1

            dwin = series[s][max(0, i - drift_window) : i + 1]
            drift = _slope(dwin)
            if drift is not None:
                drift_max_valid = True
                drift_max = max(drift_max, abs(drift))

            f[f"{s}_prev"] = prev
            f[f"{s}_change"] = change
            f[f"{s}_rate"] = rate
            f[f"{s}_rolling_mean"] = rmean
            f[f"{s}_rolling_median"] = rmed
            f[f"{s}_rolling_std"] = rstd
            f[f"{s}_rolling_mad"] = rmad
            f[f"{s}_deviation"] = dev
            f[f"{s}_historical_deviation"] = hdev
            f[f"{s}_identical_streak"] = streak
            f[f"{s}_missing_streak"] = mstreak
            f[f"{s}_sudden_change"] = sudden
            f[f"{s}_drift"] = drift
            z[s] = dev
            missing_any_streak = max(missing_any_streak, mstreak)

        # Multivariate: break of the normal inverse T-H coupling shows up as
        # same-sign z-scores (product > 0); distance aggregates all three.
        def _prod(a: float | None, b: float | None) -> float | None:
            return None if a is None or b is None else a * b

        f["temperature_humidity_relationship"] = _prod(z["temperature"], z["humidity"])
        f["temperature_pressure_relationship"] = _prod(z["temperature"], z["pressure"])
        f["humidity_pressure_relationship"] = _prod(z["humidity"], z["pressure"])

        wt = [series["temperature"][max(0, i - window) : i + 1]]
        wth = [series["humidity"][max(0, i - window) : i + 1]]
        wtp = [series["pressure"][max(0, i - window) : i + 1]]
        f["rolling_corr_th"] = _pearson(wt[0], wth[0])
        f["rolling_corr_tp"] = _pearson(wt[0], wtp[0])
        f["rolling_corr_hp"] = _pearson(wth[0], wtp[0])

        if all(v is not None for v in z.values()):
            f["multivariate_distance"] = math.sqrt(sum(v * v for v in z.values()))  # type: ignore[operator]
        else:
            f["multivariate_distance"] = None

        # Overall missing streak: trailing rows where ANY core value is missing
        overall = 0
        j = i
        while j >= 0 and any(_is_missing(series[s][j]) for s in SENSORS):
            overall += 1
            j -= 1

        f["pressure_trend"] = f["pressure_drift"]
        f["missing_value_streak"] = overall
        f["sudden_change"] = sudden_any
        f["drift_indicator"] = drift_max if drift_max_valid else None
        f.update(_time_features(stamps[i]))
        out.append(f)
    return out


def compute_latest(
    rows: list[dict],
    window: int = 6,
    drift_window: int = 24,
) -> dict:
    """Feature vector for the most recent row (real-time scoring path)."""
    if not rows:
        raise ValueError("rows must not be empty")
    return compute_features(rows, window=window, drift_window=drift_window)[-1]
