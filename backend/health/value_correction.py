from typing import Dict, Any, List
from datetime import datetime
import numpy as np
from backend.config import settings
from backend.preprocessing.feature_engineer import ExpectedValueEstimator


class ValueCorrector:
    def __init__(self):
        self.estimator = ExpectedValueEstimator(
            history_window_hours=settings.CORRECTION_WINDOW_HOURS
        )
        self.min_samples = settings.CORRECTION_MIN_SAMPLES
        self.confidence_threshold = settings.CORRECTION_CONFIDENCE_THRESHOLD

    def estimate_correction(
        self,
        station_id: str,
        current_time: datetime,
        observed: Dict[str, float],
        history: List[Dict],
        neighbor_history: Dict[str, List[Dict]] = None,
    ) -> Dict[str, Any]:
        expected = self.estimator.estimate(
            station_id=station_id,
            current_time=current_time,
            history=history,
            neighbor_history=neighbor_history,
        )

        correction_confidence = self.estimator.compute_correction_confidence(
            observed=observed,
            expected=expected,
            history=history,
        )

        should_correct = correction_confidence >= self.confidence_threshold and len(history) >= self.min_samples

        return {
            "observed": observed,
            "expected": expected,
            "corrected": expected if should_correct else observed,
            "correction_confidence": round(correction_confidence, 3),
            "correction_applied": should_correct,
            "reason": self._generate_reason(observed, expected, correction_confidence, should_correct),
        }

    def _generate_reason(
        self,
        observed: Dict,
        expected: Dict,
        confidence: float,
        applied: bool,
    ) -> str:
        if not applied:
            return "Correction confidence below threshold; observed value retained."

        diffs = []
        for param in ["temperature", "pressure", "humidity"]:
            diff = abs(observed[param] - expected[param])
            if diff > 1:
                diffs.append(f"{param}: {observed[param]:.1f} → {expected[param]:.1f}")

        if diffs:
            return f"AI-estimated correction (confidence: {confidence:.0%}): " + "; ".join(diffs)
        return "Values within normal range; no correction needed."