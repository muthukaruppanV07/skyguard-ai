import numpy as np
import pandas as pd
from typing import List, Dict, Any
from backend.config import settings


class MultivariateAnalyzer:
    def __init__(
        self,
        temp_humidity_corr: float = settings.MULTIVARIATE_TEMP_HUMIDITY_CORR,
        pressure_temp_corr: float = settings.MULTIVARIATE_PRESSURE_TEMP_CORR,
        threshold: float = settings.MULTIVARIATE_THRESHOLD,
    ):
        self.temp_humidity_corr = temp_humidity_corr
        self.pressure_temp_corr = pressure_temp_corr
        self.threshold = threshold

    def analyze(
        self,
        current: Dict,
        history: List[Dict],
    ) -> Dict[str, Any]:
        if len(history) < 20:
            return self._default_result()

        df = pd.DataFrame(history)
        df = df.sort_values("timestamp")

        th_score = self._check_temp_humidity(current, df)
        pt_score = self._check_pressure_temp(current, df)
        consistency_score = self._check_overall_consistency(current, df)

        overall = np.mean([th_score, pt_score, consistency_score])

        return {
            "multivariate_score": round(min(100, overall * 100), 2),
            "components": {
                "temp_humidity": round(th_score * 100, 2),
                "pressure_temp": round(pt_score * 100, 2),
                "overall_consistency": round(consistency_score * 100, 2),
            },
            "details": {
                "temp_humidity_expected": self._expected_humidity(current["temperature"]),
                "pressure_temp_expected": self._expected_pressure(current["temperature"]),
            },
        }

    def _expected_humidity(self, temperature: float) -> float:
        expected = 100 - (temperature - 10) * 2.5
        return np.clip(expected, 0, 100)

    def _expected_pressure(self, temperature: float) -> float:
        return 1013.25 + (temperature - 20) * 0.1

    def _check_temp_humidity(self, current: Dict, df: pd.DataFrame) -> float:
        expected_humidity = self._expected_humidity(current["temperature"])
        actual_humidity = current["humidity"]
        diff = abs(actual_humidity - expected_humidity)
        
        recent_corr = df["temperature"].rolling(20).corr(df["humidity"]).iloc[-1]
        if np.isnan(recent_corr):
            recent_corr = self.temp_humidity_corr
        
        corr_deviation = abs(recent_corr - self.temp_humidity_corr)
        
        score = min(1.0, (diff / 30.0) * 0.7 + (corr_deviation / 1.0) * 0.3)
        return score

    def _check_pressure_temp(self, current: Dict, df: pd.DataFrame) -> float:
        expected_pressure = self._expected_pressure(current["temperature"])
        actual_pressure = current["pressure"]
        diff = abs(actual_pressure - expected_pressure)
        
        score = min(1.0, diff / 10.0)
        return score

    def _check_overall_consistency(self, current: Dict, df: pd.DataFrame) -> float:
        recent = df.tail(30)
        if len(recent) < 10:
            return 0.0

        temp_humid_corr = recent["temperature"].corr(recent["humidity"])
        pressure_temp_corr = recent["pressure"].corr(recent["temperature"])
        
        if np.isnan(temp_humid_corr):
            temp_humid_corr = self.temp_humidity_corr
        if np.isnan(pressure_temp_corr):
            pressure_temp_corr = self.pressure_temp_corr

        th_dev = abs(temp_humid_corr - self.temp_humidity_corr)
        pt_dev = abs(pressure_temp_corr - self.pressure_temp_corr)

        score = min(1.0, (th_dev + pt_dev) / self.threshold)
        return score

    def _default_result(self) -> Dict:
        return {
            "multivariate_score": 0.0,
            "components": {
                "temp_humidity": 0.0,
                "pressure_temp": 0.0,
                "overall_consistency": 0.0,
            },
            "details": {},
        }


def create_multivariate_analyzer() -> MultivariateAnalyzer:
    return MultivariateAnalyzer()