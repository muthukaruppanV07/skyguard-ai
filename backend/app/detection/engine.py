"""Hybrid fusion engine: signals -> anomaly_score 0-100 -> anomaly_type.

Pipeline:
1. Gap gate (MISSING_DATA / COMMUNICATION_FAILURE) from raw Nones.
2. Run enabled detectors on the feature vector of the current row.
3. Fused score = weight-normalised mean of enabled detector scores.
4. Type = highest-priority triggered candidate (INVALID first).
5. Severity + confidence derived from fused score and detector agreement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.app.core.config import settings
from backend.app.detection import features as F
from backend.app.detection.detectors import (
    ALL_DETECTORS,
    DEFAULT_WEIGHTS,
    Detector,
    DetectorResult,
)

ANOMALY_TYPES = [
    "NORMAL",
    "TEMPERATURE_SPIKE",
    "TEMPERATURE_DROP",
    "PRESSURE_ANOMALY",
    "HUMIDITY_ANOMALY",
    "FROZEN_SENSOR",
    "SENSOR_DRIFT",
    "MISSING_DATA",
    "INVALID_DATA",
    "COMMUNICATION_FAILURE",
    "MULTIVARIATE_INCONSISTENCY",
]

# Priority for data-integrity / sensor-state types (definitive states).
# Measurement types (spikes, pressure/humidity anomalies, multivariate)
# compete by vote weight instead: a single-sensor jump also perturbs the
# joint distance, but the specific diagnosis carries more evidence.
INTEGRITY_PRIORITY = [
    "INVALID_DATA",
    "COMMUNICATION_FAILURE",
    "MISSING_DATA",
    "FROZEN_SENSOR",
    "SENSOR_DRIFT",
]

# Legacy alias (tie-break order); classification now uses
# INTEGRITY_PRIORITY for state types and vote weight otherwise.
TYPE_PRIORITY = INTEGRITY_PRIORITY + [
    "MULTIVARIATE_INCONSISTENCY",
    "TEMPERATURE_SPIKE",
    "TEMPERATURE_DROP",
    "PRESSURE_ANOMALY",
    "HUMIDITY_ANOMALY",
]


@dataclass
class EngineConfig:
    enabled: dict[str, bool] = field(default_factory=lambda: {d.name: True for d in ALL_DETECTORS for d in [d()]})
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    score_threshold: float = 50.0  # fused score >= this -> non-NORMAL type

    def __post_init__(self):
        names = {d().name for d in ALL_DETECTORS}
        unknown_e = set(self.enabled) - names
        unknown_w = set(self.weights) - names
        if unknown_e or unknown_w:
            raise ValueError(f"Unknown detectors: {sorted(unknown_e | unknown_w)}")
        wsum = sum(self.weights[d] for d in names if self.enabled.get(d, True))
        if wsum <= 0:
            raise ValueError("Enabled detector weights must sum > 0")


@dataclass
class DetectionResult:
    anomaly_type: str
    anomaly_score: float
    severity: str
    confidence: float
    detector_results: list[DetectorResult]
    evidence: dict


def _severity(score: float) -> str:
    if score >= settings.ANOMALY_THRESHOLD_CRITICAL:
        return "CRITICAL"
    if score >= settings.ANOMALY_THRESHOLD_HIGH:
        return "HIGH"
    if score >= settings.ANOMALY_THRESHOLD_SUSPICIOUS:
        return "SUSPICIOUS"
    if score >= 30:
        return "LOW"
    return "NORMAL"


class HybridEngine:
    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        self.detectors: list[Detector] = [d() for d in ALL_DETECTORS]

    @property
    def active(self) -> list[Detector]:
        return [d for d in self.detectors if self.config.enabled.get(d.name, True)]

    def detect(self, current: dict, history: list[dict]) -> DetectionResult:
        gap = self._gap_gate(current, history)
        if gap is not None:
            return gap
        feats = F.compute_latest([*history, current])
        results = [d.run(current, feats, history) for d in self.active]
        return self._fuse(results, feats)

    def _gap_gate(self, current: dict, history: list[dict]) -> DetectionResult | None:
        from backend.app.detection.detectors import _missing

        missing_sensors = [s for s in ("temperature", "pressure", "humidity") if _missing(current.get(s))]
        if not missing_sensors:
            return None
        # Trailing all-blank rows including current
        streak = 0
        for r in reversed([*history, current]):
            if all(_missing(r.get(s)) for s in ("temperature", "pressure", "humidity")):
                streak += 1
            else:
                break
        frac = len(missing_sensors) / 3.0
        if len(missing_sensors) == 3 and streak >= 3:
            atype = "COMMUNICATION_FAILURE"
            score = min(100.0, 60.0 + streak * 5.0)
        else:
            atype = "MISSING_DATA"
            score = min(100.0, 30.0 + frac * 50.0)
        results = [DetectorResult("gap_gate", score, True, {"missing": missing_sensors, "streak": streak})]
        for d in self.active:
            results.append(DetectorResult(d.name, 0.0, False, {"skipped": "gap row"}))
        return DetectionResult(
            anomaly_type=atype,
            anomaly_score=round(score, 2),
            severity=_severity(score),
            confidence=round(min(1.0, 0.5 + frac * 0.5), 3),
            detector_results=results,
            evidence={"missing_sensors": missing_sensors, "gap_streak": streak},
        )

    def _fuse(self, results: list[DetectorResult], feats: dict) -> DetectionResult:
        cfg = self.config
        # Skipped detectors (no sklearn, too little history, gap rows) carry
        # no signal: renormalise over detectors that actually ran so they
        # neither dilute nor inflate the fused score.
        ran = [r for r in results if "skipped" not in r.evidence]
        wsum = sum(cfg.weights[r.name] for r in ran) or 1.0
        fused = sum(r.score * cfg.weights[r.name] for r in ran) / wsum
        # Fault-state detectors (physical/frozen/drift) measure persistent
        # confirmed states, not momentary deviation: a strong specialist
        # signal must not be diluted by calm generalists, so it floors
        # the fused score. All values remain signal-derived.
        FAULT_STATE = {"physical", "frozen", "drift"}
        fault_scores = [r.score for r in results if r.triggered and r.name in FAULT_STATE]
        if fault_scores:
            fused = max(fused, max(fault_scores))

        by_type: dict[str, float] = {}
        for r in results:
            if r.triggered and r.candidate_type:
                by_type[r.candidate_type] = by_type.get(r.candidate_type, 0.0) + cfg.weights[r.name]
        anomaly_type = "NORMAL"
        if fused >= cfg.score_threshold and by_type:
            for t in INTEGRITY_PRIORITY:
                if t in by_type:
                    anomaly_type = t
                    break
            else:
                # Measurement types: strongest evidence weight wins;
                # TYPE_PRIORITY order breaks exact ties.
                best_w = max(by_type.values())
                tied = [t for t, w in by_type.items() if w == best_w]
                anomaly_type = next(t for t in TYPE_PRIORITY if t in tied)

        # Confidence from detector agreement + score dispersion (both signals)
        agree = sum(cfg.weights[r.name] for r in results if r.triggered) / wsum
        mean = fused
        var = sum(cfg.weights[r.name] * (r.score - mean) ** 2 for r in results) / wsum
        dispersion = min(1.0, math.sqrt(var) / 50.0)
        confidence = round(max(0.0, min(1.0, 0.5 * agree + 0.5 * (1.0 - dispersion))), 3)

        evidence = {
            "fused_score": round(fused, 2),
            "type_votes": by_type,
            "key_features": {
                k: feats.get(k)
                for k in (
                    "temperature_deviation",
                    "pressure_deviation",
                    "humidity_deviation",
                    "temperature_rate",
                    "multivariate_distance",
                    "temperature_humidity_relationship",
                    "drift_indicator",
                )
            },
        }
        return DetectionResult(
            anomaly_type=anomaly_type,
            anomaly_score=round(min(100.0, max(0.0, fused)), 2),
            severity=_severity(fused),
            confidence=confidence,
            detector_results=results,
            evidence=evidence,
        )
