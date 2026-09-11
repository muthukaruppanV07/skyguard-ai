"""Controlled evaluation: labeled episodes -> threshold baseline vs hybrid AI.

Every number is computed from generated episodes with known ground truth;
no performance value is hard-coded. Deterministic given the seed.

Episode model: `history_points` clean hourly readings, then `test_points`
with a fault injected at onset (index 0 of the test span) depending on
category. Labels: 1 for faulted points, 0 otherwise (plus a pure-normal
category that measures the false-positive rate honestly).

- spike: +12C single temperature jump at onset.
- frozen: value latched from onset through the window.
- drift: +0.8C/step temperature ramp from onset.
- missing: blank rows for 4 points from onset.
- multivariate: hot AND humid (+6C, +25%) single point.
- spatial: coherent +8C heat burst across 4 stations (evaluated per station).
- sensor_fault: stuck at plausible-but-wrong 35C with zero variation.
- weather: coherent heat burst (+6C, -10%H, -3hPa) for 4 points.
- normal: no fault at all.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.app.core.config import settings
from backend.app.detection.engine import HybridEngine
from backend.app.simulation.dataset_generator import STATION_CLIMATE, _clean_physics

CATEGORIES = ["spike", "frozen", "drift", "missing", "multivariate",
              "spatial", "sensor_fault", "weather", "normal"]

THRESHOLD = 50.0

# Traditional QC limits: hard range gates + per-hour rate gates.
RATE_LIMITS_HR = {"temperature": 5.0, "pressure": 5.0, "humidity": 10.0}


@dataclass
class EvalConfig:
    episodes_per_category: int = 2
    history_points: int = 64  # >= IF min_history (50) so the full hybrid runs
    test_points: int = 12
    step_minutes: int = 60
    seed: int = 42


@dataclass
class PointResult:
    category: str
    label: int
    threshold_score: float
    hybrid_score: float
    latency_idx: int  # index within test span


def _climate():
    return dict(STATION_CLIMATE.get("AWS001", {"base_temp": 26.0, "base_hum": 60.0,
                                               "season_amp": 4.0, "diurnal_amp": 4.5,
                                               "elev_m": 200.0}))


def _clean_series(rng: random.Random, n: int, start: datetime, step: timedelta):
    climate, state, out, ts = _climate(), {}, [], start
    for _ in range(n):
        t, p, h = _clean_physics(climate, ts, rng, state)
        out.append({"timestamp": ts, "temperature": t, "pressure": p, "humidity": h})
        ts += step
    return out


def _apply_fault(category: str, rows: list[dict]) -> list[int]:
    """Mutate test-span rows in place; return per-row labels."""
    n = len(rows)
    labels = [0] * n
    if category == "normal":
        return labels
    if category == "spike":
        rows[0]["temperature"] = round(rows[0]["temperature"] + 12.0, 2)
        labels[0] = 1
    elif category == "frozen":
        t0 = {k: rows[0][k] for k in ("temperature", "pressure", "humidity")}
        for i in range(n):
            rows[i].update(t0)
            labels[i] = 1
    elif category == "drift":
        for i in range(n):
            rows[i]["temperature"] = round(rows[i]["temperature"] + 0.8 * (i + 1), 2)
            labels[i] = 1
    elif category == "missing":
        for i in range(min(4, n)):
            rows[i].update({"temperature": None, "pressure": None, "humidity": None})
            labels[i] = 1
    elif category == "multivariate":
        rows[0]["temperature"] = round(rows[0]["temperature"] + 6.0, 2)
        rows[0]["humidity"] = round(min(100.0, rows[0]["humidity"] + 25.0), 2)
        labels[0] = 1
    elif category == "spatial":
        for i in range(min(3, n)):
            rows[i]["temperature"] = round(rows[i]["temperature"] + 8.0, 2)
            rows[i]["humidity"] = round(max(0.0, rows[i]["humidity"] - 12.0), 2)
            labels[i] = 1
    elif category == "sensor_fault":
        for i in range(n):
            rows[i].update({"temperature": 35.0, "pressure": 1000.0, "humidity": 55.0})
            labels[i] = 1
    elif category == "weather":
        for i in range(min(4, n)):
            rows[i]["temperature"] = round(rows[i]["temperature"] + 6.0, 2)
            rows[i]["humidity"] = round(max(0.0, rows[i]["humidity"] - 10.0), 2)
            rows[i]["pressure"] = round(rows[i]["pressure"] - 3.0, 2)
            labels[i] = 1
    return labels


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def threshold_score(current: dict, prev: dict | None) -> float:
    """Traditional range + rate + stuck gates. Deterministic, documented."""
    for s, lo, hi in (("temperature", settings.TEMP_MIN, settings.TEMP_MAX),
                      ("pressure", settings.PRESSURE_MIN, settings.PRESSURE_MAX),
                      ("humidity", settings.HUMIDITY_MIN, settings.HUMIDITY_MAX)):
        v = current.get(s)
        if _missing(v):
            return 100.0
        if not lo <= v <= hi:
            return 100.0
    if prev is None:
        return 0.0
    dt_h = max(1 / 60, (current["timestamp"] - prev["timestamp"]).total_seconds() / 3600.0)
    present = [s for s in ("temperature", "pressure", "humidity")
               if not _missing(current.get(s)) and not _missing(prev.get(s))]
    if not present:
        return 0.0  # no comparable pair (e.g. right after a gap): nothing to judge
    if all(current.get(s) == prev.get(s) for s in present) and len(present) == 3:
        stuck = 70.0
    else:
        stuck = 0.0
    best = 0.0
    for s in present:
        lim = RATE_LIMITS_HR[s]
        r = abs(current[s] - prev[s]) / dt_h / lim
        if r >= 1.0:
            best = max(best, min(100.0, 50.0 * r))
    return max(stuck, best)


def _confusion(y_true: list[int], y_pred: list[int]) -> dict:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    n = len(y_true) or 1
    acc = (tp + tn) / n
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return {"accuracy": round(acc, 4), "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "fpr": round(fpr, 4),
            "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}, "n": len(y_true)}


def run_evaluation(cfg: EvalConfig) -> dict:
    engine = HybridEngine()
    points: list[PointResult] = []
    lat_thr: dict[str, list] = {c: [] for c in CATEGORIES}
    lat_hyb: dict[str, list] = {c: [] for c in CATEGORIES}
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    step = timedelta(minutes=cfg.step_minutes)

    for ci, category in enumerate(CATEGORIES):
        for ep in range(cfg.episodes_per_category):
            rng = random.Random(cfg.seed + ci * 1000 + ep)
            ts = start + timedelta(days=30 * (ci * 10 + ep))
            history = _clean_series(rng, cfg.history_points, ts, step)
            test = _clean_series(rng, cfg.test_points, ts + step * cfg.history_points, step)
            labels = _apply_fault(category, test)
            hist = list(history)
            first_thr = first_hyb = None
            prev = hist[-1]
            for i, row in enumerate(test):
                t_score = threshold_score(row, prev)
                h_score = engine.detect(
                    {"timestamp": row["timestamp"], "temperature": row["temperature"],
                     "pressure": row["pressure"], "humidity": row["humidity"]}, hist).anomaly_score
                points.append(PointResult(category, labels[i], round(t_score, 2), round(h_score, 2), i))
                if labels[i] == 1:
                    if first_thr is None and t_score >= THRESHOLD:
                        first_thr = i
                    if first_hyb is None and h_score >= THRESHOLD:
                        first_hyb = i
                hist.append(row)
                prev = row
            onset = next((i for i, l in enumerate(labels) if l == 1), None)
            if onset is not None:
                lat_thr[category].append(None if first_thr is None else first_thr - onset)
                lat_hyb[category].append(None if first_hyb is None else first_hyb - onset)

    def method_metrics(getter):
        y_true = [p.label for p in points]
        y_pred = [1 if getter(p) >= THRESHOLD else 0 for p in points]
        return _confusion(y_true, y_pred)

    def latency(stat: dict[str, list]):
        det = [v for vs in stat.values() for v in vs if v is not None]
        total = sum(1 for vs in stat.values() for _ in vs)
        return {"mean_steps": round(sum(det) / len(det), 2) if det else None,
                "detected_episodes": len(det), "total_episodes": total}

    by_cat = {}
    for c in CATEGORIES:
        sub = [p for p in points if p.category == c]
        yt = [p.label for p in sub]
        by_cat[c] = {
            "threshold": _confusion(yt, [1 if p.threshold_score >= THRESHOLD else 0 for p in sub]),
            "hybrid": _confusion(yt, [1 if p.hybrid_score >= THRESHOLD else 0 for p in sub]),
            "n": len(sub),
        }
    return {
        "config": {"episodes_per_category": cfg.episodes_per_category,
                   "history_points": cfg.history_points, "test_points": cfg.test_points,
                   "step_minutes": cfg.step_minutes, "seed": cfg.seed, "threshold": THRESHOLD},
        "methods": {"threshold": method_metrics(lambda p: p.threshold_score),
                    "hybrid": method_metrics(lambda p: p.hybrid_score)},
        "latency": {"threshold": latency(lat_thr), "hybrid": latency(lat_hyb)},
        "categories": by_cat,
        "episodes": cfg.episodes_per_category * len(CATEGORIES),
    }
