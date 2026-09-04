import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.config import settings, FEATURE_COLUMNS, MODEL_FEATURE_COLUMNS


class FeatureEngineer:
    def __init__(self, window_size: int = 5, zscore_window: int = 60):
        self.window_size = window_size
        self.zscore_window = zscore_window

    def engineer_features(
        self,
        readings: List[Dict],
        station_id: str,
        expected_values: Dict[str, float] = None,
        neighbor_readings: Dict[str, List[Dict]] = None,
    ) -> pd.DataFrame:
        if not readings:
            return pd.DataFrame(columns=FEATURE_COLUMNS)

        df = pd.DataFrame(readings)
        df = df.sort_values("timestamp").reset_index(drop=True)

        df["temp_change"] = df["temperature"].diff()
        df["pressure_change"] = df["pressure"].diff()
        df["humidity_change"] = df["humidity"].diff()

        for col in ["temperature", "pressure", "humidity"]:
            df[f"{col}_rolling_mean_{self.window_size}"] = df[col].rolling(self.window_size, min_periods=1).mean()
            df[f"{col}_rolling_std_{self.window_size}"] = df[col].rolling(self.window_size, min_periods=1).std().fillna(0)
            df[f"{col}_rolling_min_{self.window_size}"] = df[col].rolling(self.window_size, min_periods=1).min()
            df[f"{col}_rolling_max_{self.window_size}"] = df[col].rolling(self.window_size, min_periods=1).max()

        for col in ["temperature", "pressure", "humidity"]:
            change_col = f"{col}_change"
            df[f"{col}_rate_of_change"] = df[change_col].rolling(self.window_size, min_periods=1).mean()

        for col in ["temperature", "pressure", "humidity"]:
            rolling_mean = df[f"{col}_rolling_mean_{self.zscore_window}"]
            rolling_std = df[f"{col}_rolling_std_{self.zscore_window}"].replace(0, 1e-6)
            df[f"{col}_zscore_{self.zscore_window}"] = (df[col] - rolling_mean) / rolling_std

        df["hour"] = df["timestamp"].dt.hour
        df["day_of_year"] = df["timestamp"].dt.dayofyear
        df["season_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365.25)
        df["season_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365.25)

        df["temp_humidity_ratio"] = df["temperature"] / (df["humidity"] + 1)
        df["pressure_temp_ratio"] = df["pressure"] / (df["temperature"] + 273.15)

        if expected_values:
            df["temp_deviation_expected"] = df["temperature"] - expected_values.get("temperature", df["temperature"])
            df["pressure_deviation_expected"] = df["pressure"] - expected_values.get("pressure", df["pressure"])
            df["humidity_deviation_expected"] = df["humidity"] - expected_values.get("humidity", df["humidity"])
        else:
            df["temp_deviation_expected"] = 0.0
            df["pressure_deviation_expected"] = 0.0
            df["humidity_deviation_expected"] = 0.0

        if neighbor_readings:
            df = self._add_spatial_features(df, neighbor_readings)

        for col in FEATURE_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0

        return df[FEATURE_COLUMNS]

    def _add_spatial_features(self, df: pd.DataFrame, neighbor_readings: Dict[str, List[Dict]]) -> pd.DataFrame:
        for neighbor_id, readings in neighbor_readings.items():
            if not readings:
                continue
            n_df = pd.DataFrame(readings)
            n_df = n_df.sort_values("timestamp")
            
            for col in ["temperature", "pressure", "humidity"]:
                n_df = n_df.set_index("timestamp")[col].resample("1min").interpolate().reset_index()
                
                merged = pd.merge_asof(
                    df[["timestamp", col]].sort_values("timestamp"),
                    n_df.sort_values("timestamp"),
                    on="timestamp",
                    direction="nearest",
                    suffixes=("", f"_{neighbor_id}"),
                )
                df[f"{col}_neighbor_{neighbor_id}"] = merged[f"{col}_{neighbor_id}"].values
                df[f"{col}_spatial_diff_{neighbor_id}"] = df[col] - df[f"{col}_neighbor_{neighbor_id}"]
        
        return df

    def get_model_features(self, df: pd.DataFrame) -> np.ndarray:
        available_cols = [c for c in MODEL_FEATURE_COLUMNS if c in df.columns]
        return df[available_cols].fillna(0).values

    def engineer_single(
        self,
        current: Dict,
        history: List[Dict],
        expected_values: Dict = None,
        neighbor_current: Dict = None,
    ) -> np.ndarray:
        all_readings = history + [current]
        df = self.engineer_features(all_readings, current["station_id"], expected_values)
        return self.get_model_features(df.iloc[[-1]])[0]


class ExpectedValueEstimator:
    def __init__(self, history_window_hours: int = 24):
        self.history_window_hours = history_window_hours

    def estimate(
        self,
        station_id: str,
        current_time: datetime,
        history: List[Dict],
        neighbor_history: Dict[str, List[Dict]] = None,
    ) -> Dict[str, float]:
        if not history:
            return {"temperature": 25.0, "pressure": 1013.25, "humidity": 60.0}

        cutoff = current_time - timedelta(hours=self.history_window_hours)
        recent = [r for r in history if r["timestamp"] >= cutoff]
        
        if len(recent) < 10:
            recent = history[-50:]

        df = pd.DataFrame(recent)
        df = df.sort_values("timestamp")

        temp_trend = self._fit_trend(df["temperature"].values)
        pressure_trend = self._fit_trend(df["pressure"].values)
        humidity_trend = self._fit_trend(df["humidity"].values)

        last_temp = df["temperature"].iloc[-1]
        last_pressure = df["pressure"].iloc[-1]
        last_humidity = df["humidity"].iloc[-1]

        hour = current_time.hour
        temp_cycle = 8.0 * np.sin(2 * np.pi * (hour - 6) / 24)
        pressure_cycle = 1.5 * np.sin(2 * np.pi * hour / 12)
        humidity_cycle = -10.0 * np.sin(2 * np.pi * (hour - 6) / 24)

        expected_temp = last_temp + temp_trend + temp_cycle * 0.1
        expected_pressure = last_pressure + pressure_trend + pressure_cycle * 0.1
        expected_humidity = np.clip(last_humidity + humidity_trend + humidity_cycle * 0.1, 0, 100)

        if neighbor_history:
            spatial_temp = self._spatial_estimate("temperature", current_time, neighbor_history)
            spatial_pressure = self._spatial_estimate("pressure", current_time, neighbor_history)
            spatial_humidity = self._spatial_estimate("humidity", current_time, neighbor_history)
            
            expected_temp = 0.7 * expected_temp + 0.3 * spatial_temp
            expected_pressure = 0.7 * expected_pressure + 0.3 * spatial_pressure
            expected_humidity = 0.7 * expected_humidity + 0.3 * spatial_humidity

        return {
            "temperature": round(expected_temp, 2),
            "pressure": round(expected_pressure, 2),
            "humidity": round(expected_humidity, 2),
        }

    def _fit_trend(self, values: np.ndarray) -> float:
        if len(values) < 5:
            return 0.0
        x = np.arange(len(values))
        coeffs = np.polyfit(x, values, 1)
        return coeffs[0]

    def _spatial_estimate(
        self,
        parameter: str,
        current_time: datetime,
        neighbor_history: Dict[str, List[Dict]],
    ) -> float:
        estimates = []
        for neighbor_id, readings in neighbor_history.items():
            if not readings:
                continue
            cutoff = current_time - timedelta(hours=1)
            recent = [r for r in readings if r["timestamp"] >= cutoff]
            if recent:
                estimates.append(np.mean([r[parameter] for r in recent]))
        
        return np.mean(estimates) if estimates else 0.0

    def compute_correction_confidence(
        self,
        observed: Dict[str, float],
        expected: Dict[str, float],
        history: List[Dict],
    ) -> float:
        if not history or len(history) < 20:
            return 0.5

        df = pd.DataFrame(history[-100:])
        temp_mae = np.mean(np.abs(df["temperature"].diff().dropna()))
        pressure_mae = np.mean(np.abs(df["pressure"].diff().dropna()))
        humidity_mae = np.mean(np.abs(df["humidity"].diff().dropna()))

        temp_diff = abs(observed["temperature"] - expected["temperature"])
        pressure_diff = abs(observed["pressure"] - expected["pressure"])
        humidity_diff = abs(observed["humidity"] - expected["humidity"])

        temp_conf = 1.0 / (1.0 + temp_diff / max(temp_mae, 0.1))
        pressure_conf = 1.0 / (1.0 + pressure_diff / max(pressure_mae, 0.01))
        humidity_conf = 1.0 / (1.0 + humidity_diff / max(humidity_mae, 0.1))

        return round((temp_conf + pressure_conf + humidity_conf) / 3, 3)


from datetime import timedelta