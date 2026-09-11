"""Modular hybrid detectors (SIH 26073). T/P/H only.

Each detector maps raw signals to a 0-100 score computed from the
signal itself (magnitudes, ratios, streak lengths) — never a fixed
constant per anomaly type. All handle None/NaN safely.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from backend.app.core.config import settings

SENSORS = ("temperature", "pressure", "humidity")

BOUNDS = {
    "temperature": (settings.TEMP_MIN, settings.TEMP_MAX),
    "pressure": (settings.PRESSURE_MIN, settings.PRESSURE_MAX),
    "humidity": (settings.HUMIDITY_MIN, settings.HUMIDITY_MAX),
}

# Per-minute rate limits (max plausible sustained synoptic rates: a real
# atmosphere rarely moves faster than ~3C/hr, ~3hPa/hr or ~15%/hr; sensor
# faults exceed these by an order of magnitude within one step)
RATE_LIMITS = {"temperature": 0.05, "pressure": 0.05, "humidity": 0.25}

# Drift slope limit in units per hour
DRIFT_LIMITS = {"temperature": 0.5, "pressure": 1.0, "humidity": 2.0}

FROZEN_STREAK_TRIGGER = 6
FROZEN_STREAK_FULL = 12  # streak length scoring 100 (score = 100 * streak / FULL)


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


@dataclass
class DetectorResult:
    name: str
    score: float  # 0-100, derived from signals
    triggered: bool
    evidence: dict = field(default_factory=dict)
    candidate_type: str | None = None  # anomaly-type hint when triggered


class Detector:
    name = "base"
    enabled = True

    def run(self, current: dict, feats: dict, history: list[dict]) -> DetectorResult:
        raise NotImplementedError


def _window_values(history: list[dict], sensor: str, n: int) -> list[float]:
    vals = [r.get(sensor) for r in history[-n:]]
    return [v for v in vals if not _missing(v)]


class PhysicalValidator(Detector):
    """IMD plausibility ranges. Score scales with fraction of sensors violated."""

    name = "physical"

    def run(self, current, feats, history):
        bad = {}
        for s in SENSORS:
            v = current.get(s)
            if _missing(v):
                continue
            lo, hi = BOUNDS[s]
            if not lo <= v <= hi:
                bad[s] = {"value": v, "bounds": [lo, hi]}
        score = 100.0 * len(bad) / len(SENSORS)
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=bool(bad),
            evidence={"violations": bad},
            candidate_type="INVALID_DATA" if bad else None,
        )


class RollingStatisticalDetector(Detector):
    """Classical z-score vs trailing rolling mean/std. Score from max |z|."""

    name = "statistical"

    def run(self, current, feats, history):
        best, zs = 0.0, {}
        for s in SENSORS:
            z = feats.get(f"{s}_deviation")
            if z is None or (isinstance(z, float) and math.isnan(z)):
                continue
            zs[s] = z
            best = max(best, abs(z))
        score = min(100.0, best / 6.0 * 100.0)
        top = max(zs, key=lambda k: abs(zs[k])) if zs else None
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=best >= 3.0,
            evidence={"z_scores": zs, "max_abs_z": best},
            candidate_type=_sensor_to_spike(top, zs.get(top, 0) if top else 0) if best >= 3.0 else None,
        )


class RobustZDetector(Detector):
    """MAD-based robust z (0.6745*(x-median)/MAD). Resists contaminated windows."""

    name = "robust_z"

    def run(self, current, feats, history, window: int = 12):
        best, zs = 0.0, {}
        for s in SENSORS:
            v = current.get(s)
            vals = _window_values(history, s, window)
            if _missing(v) or len(vals) < 3:
                continue
            med = statistics.median(vals)
            mad = statistics.median([abs(x - med) for x in vals])
            if mad == 0:
                continue
            z = 0.6745 * (v - med) / mad
            zs[s] = z
            best = max(best, abs(z))
        score = min(100.0, best / 6.0 * 100.0)
        top = max(zs, key=lambda k: abs(zs[k])) if zs else None
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=best >= 3.5,
            evidence={"robust_z": zs, "max_abs_z": best},
            candidate_type=_sensor_to_spike(top, zs.get(top, 0) if top else 0) if best >= 3.5 else None,
        )


class RateOfChangeDetector(Detector):
    """Per-minute rate vs synoptic limits. Score from worst limit ratio."""

    name = "rate"

    def run(self, current, feats, history):
        best, rates = 0.0, {}
        for s in SENSORS:
            r = feats.get(f"{s}_rate")
            if r is None or (isinstance(r, float) and math.isnan(r)):
                continue
            ratio = abs(r) / RATE_LIMITS[s]
            rates[s] = {"rate_per_min": r, "limit": RATE_LIMITS[s], "ratio": ratio}
            best = max(best, ratio)
        score = min(100.0, best / 5.0 * 100.0)
        top = max(rates, key=lambda k: rates[k]["ratio"]) if rates else None
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=best >= 2.0,
            evidence={"rates": rates, "max_ratio": best},
            candidate_type=_sensor_to_spike(top, rates[top]["rate_per_min"] if top else 0) if best >= 2.0 else None,
        )


class IsolationForestDetector(Detector):
    """Unsupervised outlier score on T/P/H, trained on history excl. current."""

    name = "isolation_forest"
    min_history = 50

    def run(self, current, feats, history):
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            return DetectorResult(self.name, 0.0, False, {"skipped": "sklearn not installed"})
        vec = [current.get(s) for s in SENSORS]
        if any(_missing(v) for v in vec):
            return DetectorResult(self.name, 0.0, False, {"skipped": "current has missing values"})
        X = [[r.get(s) for s in SENSORS] for r in history]
        X = [row for row in X if not any(_missing(v) for v in row)]
        if len(X) < self.min_history:
            return DetectorResult(
                self.name, 0.0, False, {"skipped": "insufficient_history", "rows": len(X)}
            )
        clf = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        clf.fit(X)
        train_scores = clf.score_samples(X)
        current_score = float(clf.score_samples([vec])[0])
        mean = statistics.fmean(train_scores)
        std = statistics.pstdev(train_scores) or 1e-9
        z = (mean - current_score) / std
        score = min(100.0, max(0.0, z / 3.0 * 100.0))
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=z >= 2.0,
            evidence={"train_mean": mean, "train_std": std, "current_score": current_score, "z": z},
            candidate_type=None,  # generic outlier signal; typing left to specialists
        )


class TemporalAnalyzer(Detector):
    """Spike/drop with temporal context: jump size relative to local variability."""

    name = "temporal"

    def run(self, current, feats, history):
        best, detail = 0.0, {}
        for s in SENSORS:
            change = feats.get(f"{s}_change")
            rstd = feats.get(f"{s}_rolling_std")
            if change is None or rstd is None or rstd == 0:
                continue
            mag = abs(change) / rstd
            detail[s] = {"change": change, "rolling_std": rstd, "magnitude": mag}
            best = max(best, mag)
        score = min(100.0, best / 6.0 * 100.0)
        top = max(detail, key=lambda k: detail[k]["magnitude"]) if detail else None
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=best >= 3.0,
            evidence={"magnitudes": detail, "max": best},
            candidate_type=_sensor_to_spike(top, detail[top]["change"] if top else 0) if best >= 3.0 else None,
        )


class MultivariateAnalyzer(Detector):
    """T-H-P consistency: joint distance + broken inverse T-H coupling."""

    name = "multivariate"

    def run(self, current, feats, history):
        dist = feats.get("multivariate_distance")
        th = feats.get("temperature_humidity_relationship")
        parts = []
        if dist is not None and not (isinstance(dist, float) and math.isnan(dist)):
            parts.append(dist / 6.0 * 100.0)
        if th is not None and th > 0 and not (isinstance(th, float) and math.isnan(th)):
            parts.append(min(100.0, th / 3.0 * 100.0))
        score = min(100.0, max(parts) if parts else 0.0)
        triggered = (dist is not None and dist >= 3.0) or (th is not None and th >= 2.0)
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=bool(triggered),
            evidence={"distance": dist, "th_relationship": th},
            candidate_type="MULTIVARIATE_INCONSISTENCY" if triggered else None,
        )


class FrozenSensorDetector(Detector):
    """Stuck sensor: score grows with identical-value streak length."""

    name = "frozen"

    def run(self, current, feats, history):
        best_streak, streaks = 0, {}
        for s in SENSORS:
            st = feats.get(f"{s}_identical_streak") or 0
            streaks[s] = st
            best_streak = max(best_streak, st)
        score = min(100.0, best_streak / FROZEN_STREAK_FULL * 100.0)
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=best_streak >= FROZEN_STREAK_TRIGGER,
            evidence={"streaks": streaks, "max_streak": best_streak},
            candidate_type="FROZEN_SENSOR" if best_streak >= FROZEN_STREAK_TRIGGER else None,
        )


class DriftDetector(Detector):
    """Calibration drift: sustained slope vs per-hour limits.

    Drift is a long-horizon fault: fewer than 12 valid points in the
    window is insufficient evidence (a short slice of the normal diurnal
    cycle can look steep), so the detector abstains instead of guessing.
    """

    name = "drift"
    min_points = 12

    def run(self, current, feats, history, drift_window: int = 24):
        n_points = len(history) + 1
        if n_points < self.min_points:
            return DetectorResult(
                self.name, 0.0, False,
                {"skipped": "short_window", "points": n_points, "min_points": self.min_points},
            )
        best, slopes = 0.0, {}
        for s in SENSORS:
            slope = feats.get(f"{s}_drift")
            if slope is None or (isinstance(slope, float) and math.isnan(slope)):
                continue
            per_hour = abs(slope)  # features step ~hourly in eval; ratio is what matters
            ratio = per_hour / DRIFT_LIMITS[s]
            slopes[s] = {"slope_per_step": slope, "ratio": ratio}
            best = max(best, ratio)
        score = min(100.0, best / 2.0 * 100.0)
        return DetectorResult(
            name=self.name,
            score=score,
            triggered=best >= 1.5,
            evidence={"slopes": slopes, "max_ratio": best},
            candidate_type="SENSOR_DRIFT" if best >= 1.5 else None,
        )


def _sensor_to_spike(sensor: str | None, signed: float) -> str | None:
    if sensor is None:
        return None
    if sensor == "temperature":
        return "TEMPERATURE_SPIKE" if signed >= 0 else "TEMPERATURE_DROP"
    if sensor == "pressure":
        return "PRESSURE_ANOMALY"
    if sensor == "humidity":
        return "HUMIDITY_ANOMALY"
    return None


ALL_DETECTORS: tuple[type[Detector], ...] = (
    PhysicalValidator,
    RollingStatisticalDetector,
    RobustZDetector,
    RateOfChangeDetector,
    IsolationForestDetector,
    TemporalAnalyzer,
    MultivariateAnalyzer,
    FrozenSensorDetector,
    DriftDetector,
)

DEFAULT_WEIGHTS = {
    "physical": 0.20,
    "statistical": 0.12,
    "robust_z": 0.12,
    "rate": 0.10,
    "isolation_forest": 0.12,
    "temporal": 0.10,
    "multivariate": 0.12,
    "frozen": 0.06,
    "drift": 0.06,
}
