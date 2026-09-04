import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from backend.config import settings


class TemporalAnalyzer:
    def __init__(
        self,
        window_minutes: int = settings.TEMPORAL_WINDOW_MINUTES,
        zscore_threshold: float = settings.TEMPORAL_ZSCORE_THRESHOLD,
        drift_window_hours: int = settings.DRIFT_WINDOW_HOURS,
        drift_threshold_per_hour: float = settings.DRIFT_THRESHOLD_PER_HOUR,
    ):
        self.window_minutes = window_minutes
        self.zscore_threshold = zscore_threshold
        self.drift_window_hours = drift_window_hours
        self.drift_threshold_per_hour = drift_threshold_per_hour

    def analyze(
        self,
        current: Dict,
        history: List[Dict],
    ) -> Dict[str, Any]:
        if len(history) < 10:
            return self._default_result()

        df = pd.DataFrame(history)
        df = df.sort_values("timestamp")
        
        cutoff = current["timestamp"] - timedelta(minutes=self.window_minutes)
        recent = df[df["timestamp"] >= cutoff]
        
        if len(recent) < 5:
            return self._default_result()

        spike_scores = self._detect_spikes(current, recent)
        drift_scores = self._detect_drift(df)
        persistence_scores = self._detect_persistence(recent)
        rate_scores = self._detect_unusual_rate(current, recent)

        overall_score = np.mean([
            spike_scores["overall"],
            drift_scores["overall"],
            persistence_scores["overall"],
            rate_scores["overall"],
        ])

        return {
            "temporal_score": round(min(100, overall_score * 100), 2),
            "components": {
                "spike": round(spike_scores["overall"] * 100, 2),
                "drift": round(drift_scores["overall"] * 100, 2),
                "persistence": round(persistence_scores["overall"] * 100, 2),
                "rate_of_change": round(rate_scores["overall"] * 100, 2),
            },
            "details": {
                "spike": spike_scores,
                "drift": drift_scores,
                "persistence": persistence_scores,
                "rate_of_change": rate_scores,
            },
        }

    def _detect_spikes(self, current: Dict, recent: pd.DataFrame) -> Dict:
        scores = {}
        for param in ["temperature", "pressure", "humidity"]:
            values = recent[param].values
            mean_val = np.mean(values)
            std_val = np.std(values)
            
            if std_val > 0:
                zscore = abs(current[param] - mean_val) / std_val
                scores[param] = min(1.0, zscore / self.zscore_threshold)
            else:
                scores[param] = 0.0

        return {
            "overall": np.mean(list(scores.values())),
            "per_parameter": scores,
        }

    def _detect_drift(self, df: pd.DataFrame) -> Dict:
        if len(df) < self.drift_window_hours * 60 / 5:
            return {"overall": 0.0, "per_parameter": {}}

        cutoff = df["timestamp"].iloc[-1] - timedelta(hours=self.drift_window_hours)
        window_df = df[df["timestamp"] >= cutoff]
        
        if len(window_df) < 10:
            return {"overall": 0.0, "per_parameter": {}}

        scores = {}
        for param in ["temperature", "pressure", "humidity"]:
            x = np.arange(len(window_df))
            y = window_df[param].values
            coeffs = np.polyfit(x, y, 1)
            slope_per_hour = coeffs[0] * (60 / 5)
            
            scores[param] = min(1.0, abs(slope_per_hour) / self.drift_threshold_per_hour)

        return {
            "overall": np.mean(list(scores.values())),
            "per_parameter": scores,
        }

    def _detect_persistence(self, recent: pd.DataFrame) -> Dict:
        scores = {}
        for param in ["temperature", "pressure", "humidity"]:
            values = recent[param].values
            diffs = np.diff(values)
            zero_diffs = np.sum(np.abs(diffs) < 0.01)
            persistence_ratio = zero_diffs / len(diffs) if len(diffs) > 0 else 0
            scores[param] = persistence_ratio

        return {
            "overall": np.mean(list(scores.values())),
            "per_parameter": scores,
        }

    def _detect_unusual_rate(self, current: Dict, recent: pd.DataFrame) -> Dict:
        scores = {}
        for param in ["temperature", "pressure", "humidity"]:
            values = recent[param].values
            if len(values) > 1:
                rates = np.diff(values)
                mean_rate = np.mean(np.abs(rates))
                std_rate = np.std(rates)
                
                current_rate = abs(current[param] - values[-1])
                
                if std_rate > 0:
                    zscore = abs(current_rate - mean_rate) / std_rate
                    scores[param] = min(1.0, zscore / 3.0)
                else:
                    scores[param] = 0.0
            else:
                scores[param] = 0.0

        return {
            "overall": np.mean(list(scores.values())),
            "per_parameter": scores,
        }

    def _default_result(self) -> Dict:
        return {
            "temporal_score": 0.0,
            "components": {
                "spike": 0.0,
                "drift": 0.0,
                "persistence": 0.0,
                "rate_of_change": 0.0,
            },
            "details": {},
        }


def create_temporal_analyzer() -> TemporalAnalyzer:
    return TemporalAnalyzer()