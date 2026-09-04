import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
from backend.config import settings
from backend.preprocessing.validator import DataValidator


class RuleEngine:
    def __init__(self):
        self.validator = DataValidator()
        self.weights = {
            "range_check": 0.2,
            "rate_of_change": 0.2,
            "frozen_check": 0.2,
            "gap_check": 0.15,
            "duplicate_check": 0.1,
            "multivariate_consistency": 0.15,
        }

    def check_range(self, temperature: float, pressure: float, humidity: float) -> float:
        score = 0.0
        if temperature < settings.TEMP_MIN or temperature > settings.TEMP_MAX:
            score += 0.5
        if pressure < settings.PRESSURE_MIN or pressure > settings.PRESSURE_MAX:
            score += 0.3
        if humidity < settings.HUMIDITY_MIN or humidity > settings.HUMIDITY_MAX:
            score += 0.2
        return min(1.0, score)

    def check_rate_of_change(
        self,
        current: Dict,
        previous: List[Dict],
    ) -> float:
        if not previous:
            return 0.0
        
        prev = previous[-1]
        time_diff = (current["timestamp"] - prev["timestamp"]).total_seconds() / 60
        if time_diff <= 0:
            return 0.0

        temp_rate = abs(current["temperature"] - prev["temperature"]) / time_diff
        pressure_rate = abs(current["pressure"] - prev["pressure"]) / time_diff
        humidity_rate = abs(current["humidity"] - prev["humidity"]) / time_diff

        score = 0.0
        if temp_rate > settings.MAX_TEMP_CHANGE_PER_MIN:
            score += min(1.0, temp_rate / settings.MAX_TEMP_CHANGE_PER_MIN) * 0.4
        if pressure_rate > settings.MAX_PRESSURE_CHANGE_PER_MIN:
            score += min(1.0, pressure_rate / settings.MAX_PRESSURE_CHANGE_PER_MIN) * 0.3
        if humidity_rate > settings.MAX_HUMIDITY_CHANGE_PER_MIN:
            score += min(1.0, humidity_rate / settings.MAX_HUMIDITY_CHANGE_PER_MIN) * 0.3

        return min(1.0, score)

    def check_frozen(self, history: List[Dict]) -> float:
        if len(history) < settings.FROZEN_THRESHOLD_MINUTES:
            return 0.0

        recent = history[-settings.FROZEN_THRESHOLD_MINUTES:]
        temp_std = np.std([r["temperature"] for r in recent])
        pressure_std = np.std([r["pressure"] for r in recent])
        humidity_std = np.std([r["humidity"] for r in recent])

        score = 0.0
        if temp_std < 0.01:
            score += 0.4
        if pressure_std < 0.01:
            score += 0.3
        if humidity_std < 0.01:
            score += 0.3

        return min(1.0, score)

    def check_gaps(self, history: List[Dict], expected_interval: int = 1) -> float:
        if len(history) < 2:
            return 0.0

        sorted_hist = sorted(history, key=lambda x: x["timestamp"])
        max_gap = 0
        for i in range(1, len(sorted_hist)):
            if sorted_hist[i-1]["station_id"] == sorted_hist[i]["station_id"]:
                gap = (sorted_hist[i]["timestamp"] - sorted_hist[i-1]["timestamp"]).total_seconds() / 60
                max_gap = max(max_gap, gap)

        if max_gap > expected_interval * 2:
            return min(1.0, (max_gap - expected_interval) / (expected_interval * 10))
        return 0.0

    def check_duplicates(self, history: List[Dict]) -> float:
        seen = set()
        duplicates = 0
        for r in history:
            key = (r["station_id"], r["timestamp"])
            if key in seen:
                duplicates += 1
            seen.add(key)
        
        if duplicates > 0:
            return min(1.0, duplicates / 5.0)
        return 0.0

    def check_multivariate_consistency(
        self,
        temperature: float,
        pressure: float,
        humidity: float,
    ) -> float:
        expected_humidity = 100 - (temperature - 10) * 2.5
        expected_humidity = np.clip(expected_humidity, 0, 100)
        humidity_diff = abs(humidity - expected_humidity)

        expected_pressure_change = (temperature - 20) * 0.1
        pressure_diff = abs(pressure - (1013.25 + expected_pressure_change))

        score = 0.0
        if humidity_diff > 20:
            score += min(1.0, humidity_diff / 50) * 0.6
        if pressure_diff > 5:
            score += min(1.0, pressure_diff / 20) * 0.4

        return min(1.0, score)

    def compute_score(
        self,
        current: Dict,
        history: List[Dict],
        neighbor_data: Dict[str, List[Dict]] = None,
    ) -> Dict[str, Any]:
        range_score = self.check_range(
            current["temperature"], current["pressure"], current["humidity"]
        )
        rate_score = self.check_rate_of_change(current, history)
        frozen_score = self.check_frozen(history)
        gap_score = self.check_gaps(history)
        duplicate_score = self.check_duplicates(history)
        mv_score = self.check_multivariate_consistency(
            current["temperature"], current["pressure"], current["humidity"]
        )

        weighted_score = (
            self.weights["range_check"] * range_score +
            self.weights["rate_of_change"] * rate_score +
            self.weights["frozen_check"] * frozen_score +
            self.weights["gap_check"] * gap_score +
            self.weights["duplicate_check"] * duplicate_score +
            self.weights["multivariate_consistency"] * mv_score
        )

        final_score = min(100, weighted_score * 100)

        return {
            "rule_score": round(final_score, 2),
            "components": {
                "range_check": round(range_score * 100, 2),
                "rate_of_change": round(rate_score * 100, 2),
                "frozen_check": round(frozen_score * 100, 2),
                "gap_check": round(gap_score * 100, 2),
                "duplicate_check": round(duplicate_score * 100, 2),
                "multivariate_consistency": round(mv_score * 100, 2),
            },
            "details": {
                "range_violated": range_score > 0,
                "rate_violated": rate_score > 0,
                "frozen_detected": frozen_score > 0,
                "gap_detected": gap_score > 0,
                "duplicate_detected": duplicate_score > 0,
                "multivariate_violated": mv_score > 0,
            },
        }


def create_rule_engine() -> RuleEngine:
    return RuleEngine()