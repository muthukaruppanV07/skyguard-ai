import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque

from backend.config import settings
from backend.simulation.aws_simulator import WeatherState


@dataclass
class EngineeredFeatures:
    station_id: str
    timestamp: datetime

    temperature: float
    pressure: float
    humidity: float

    temp_change_1m: float = 0.0
    temp_change_5m: float = 0.0
    temp_change_15m: float = 0.0
    pressure_change_1m: float = 0.0
    pressure_change_5m: float = 0.0
    humidity_change_1m: float = 0.0
    humidity_change_5m: float = 0.0

    temp_rolling_mean_5: float = 0.0
    temp_rolling_std_5: float = 0.0
    temp_rolling_min_5: float = 0.0
    temp_rolling_max_5: float = 0.0
    pressure_rolling_mean_5: float = 0.0
    pressure_rolling_std_5: float = 0.0
    humidity_rolling_mean_5: float = 0.0
    humidity_rolling_std_5: float = 0.0

    temp_zscore_5: float = 0.0
    pressure_zscore_5: float = 0.0
    humidity_zscore_5: float = 0.0

    temp_dev_from_ma_5: float = 0.0
    pressure_dev_from_ma_5: float = 0.0
    humidity_dev_from_ma_5: float = 0.0

    temp_rate_of_change: float = 0.0
    pressure_rate_of_change: float = 0.0
    humidity_rate_of_change: float = 0.0

    hour_of_day: int = 0
    day_of_year: int = 0
    month: int = 0
    is_daytime: int = 0

    temp_humidity_ratio: float = 0.0
    temp_pressure_ratio: float = 0.0
    humidity_pressure_ratio: float = 0.0
    dew_point: float = 0.0
    heat_index: float = 0.0

    station_temp_deviation: float = 0.0
    station_pressure_deviation: float = 0.0
    station_humidity_deviation: float = 0.0

    def to_array(self) -> np.ndarray:
        return np.array([
            self.temp_change_1m, self.temp_change_5m, self.temp_change_15m,
            self.pressure_change_1m, self.pressure_change_5m,
            self.humidity_change_1m, self.humidity_change_5m,
            self.temp_rolling_mean_5, self.temp_rolling_std_5,
            self.temp_rolling_min_5, self.temp_rolling_max_5,
            self.pressure_rolling_mean_5, self.pressure_rolling_std_5,
            self.humidity_rolling_mean_5, self.humidity_rolling_std_5,
            self.temp_zscore_5, self.pressure_zscore_5, self.humidity_zscore_5,
            self.temp_dev_from_ma_5, self.pressure_dev_from_ma_5, self.humidity_dev_from_ma_5,
            self.temp_rate_of_change, self.pressure_rate_of_change, self.humidity_rate_of_change,
            self.hour_of_day, self.day_of_year, self.month, self.is_daytime,
            self.temp_humidity_ratio, self.temp_pressure_ratio, self.humidity_pressure_ratio,
            self.dew_point, self.heat_index,
            self.station_temp_deviation, self.station_pressure_deviation, self.station_humidity_deviation
        ])

    def to_dict(self) -> Dict[str, float]:
        return {
            "temp_change_1m": self.temp_change_1m,
            "temp_change_5m": self.temp_change_5m,
            "temp_change_15m": self.temp_change_15m,
            "pressure_change_1m": self.pressure_change_1m,
            "pressure_change_5m": self.pressure_change_5m,
            "humidity_change_1m": self.humidity_change_1m,
            "humidity_change_5m": self.humidity_change_5m,
            "temp_rolling_mean_5": self.temp_rolling_mean_5,
            "temp_rolling_std_5": self.temp_rolling_std_5,
            "temp_rolling_min_5": self.temp_rolling_min_5,
            "temp_rolling_max_5": self.temp_rolling_max_5,
            "pressure_rolling_mean_5": self.pressure_rolling_mean_5,
            "pressure_rolling_std_5": self.pressure_rolling_std_5,
            "humidity_rolling_mean_5": self.humidity_rolling_mean_5,
            "humidity_rolling_std_5": self.humidity_rolling_std_5,
            "temp_zscore_5": self.temp_zscore_5,
            "pressure_zscore_5": self.pressure_zscore_5,
            "humidity_zscore_5": self.humidity_zscore_5,
            "temp_dev_from_ma_5": self.temp_dev_from_ma_5,
            "pressure_dev_from_ma_5": self.pressure_dev_from_ma_5,
            "humidity_dev_from_ma_5": self.humidity_dev_from_ma_5,
            "temp_rate_of_change": self.temp_rate_of_change,
            "pressure_rate_of_change": self.pressure_rate_of_change,
            "humidity_rate_of_change": self.humidity_rate_of_change,
            "hour_of_day": self.hour_of_day,
            "day_of_year": self.day_of_year,
            "month": self.month,
            "is_daytime": self.is_daytime,
            "temp_humidity_ratio": self.temp_humidity_ratio,
            "temp_pressure_ratio": self.temp_pressure_ratio,
            "humidity_pressure_ratio": self.humidity_pressure_ratio,
            "dew_point": self.dew_point,
            "heat_index": self.heat_index,
            "station_temp_deviation": self.station_temp_deviation,
            "station_pressure_deviation": self.station_pressure_deviation,
            "station_humidity_deviation": self.station_humidity_deviation,
        }

    @staticmethod
    def feature_names() -> List[str]:
        return [
            "temp_change_1m", "temp_change_5m", "temp_change_15m",
            "pressure_change_1m", "pressure_change_5m",
            "humidity_change_1m", "humidity_change_5m",
            "temp_rolling_mean_5", "temp_rolling_std_5",
            "temp_rolling_min_5", "temp_rolling_max_5",
            "pressure_rolling_mean_5", "pressure_rolling_std_5",
            "humidity_rolling_mean_5", "humidity_rolling_std_5",
            "temp_zscore_5", "pressure_zscore_5", "humidity_zscore_5",
            "temp_dev_from_ma_5", "pressure_dev_from_ma_5", "humidity_dev_from_ma_5",
            "temp_rate_of_change", "pressure_rate_of_change", "humidity_rate_of_change",
            "hour_of_day", "day_of_year", "month", "is_daytime",
            "temp_humidity_ratio", "temp_pressure_ratio", "humidity_pressure_ratio",
            "dew_point", "heat_index",
            "station_temp_deviation", "station_pressure_deviation", "station_humidity_deviation"
        ]


class FeatureEngineer:
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.station_buffers: Dict[str, deque] = {}
        self.station_stats: Dict[str, Dict] = {}

    def _get_buffer(self, station_id: str) -> deque:
        if station_id not in self.station_buffers:
            self.station_buffers[station_id] = deque(maxlen=self.window_size)
        return self.station_buffers[station_id]

    def _calculate_dew_point(self, temp: float, humidity: float) -> float:
        if humidity <= 0:
            return -50.0
        a = 17.27
        b = 237.7
        alpha = ((a * temp) / (b + temp)) + np.log(humidity / 100.0)
        return (b * alpha) / (a - alpha)

    def _calculate_heat_index(self, temp: float, humidity: float) -> float:
        if temp < 27:
            return temp
        hi = -8.78469475556 + 1.61139411 * temp + 2.33854883889 * humidity \
             - 0.14611605 * temp * humidity - 0.012308094 * temp**2 \
             - 0.0164248277778 * humidity**2 + 0.002211732 * temp**2 * humidity \
             + 0.00072546 * temp * humidity**2 - 0.000003582 * temp**2 * humidity**2
        return hi

    def engineer_features(self, station_id: str, reading: WeatherState,
                          neighbor_readings: Optional[Dict[str, WeatherState]] = None) -> EngineeredFeatures:
        buffer = self._get_buffer(station_id)
        buffer.append(reading)

        features = EngineeredFeatures(
            station_id=station_id,
            timestamp=reading.timestamp,
            temperature=reading.temperature,
            pressure=reading.pressure,
            humidity=reading.humidity
        )

        if len(buffer) >= 2:
            prev = buffer[-2]
            time_diff = (reading.timestamp - prev.timestamp).total_seconds() / 60.0
            if time_diff > 0:
                features.temp_change_1m = reading.temperature - prev.temperature
                features.pressure_change_1m = reading.pressure - prev.pressure
                features.humidity_change_1m = reading.humidity - prev.humidity
                features.temp_rate_of_change = features.temp_change_1m / time_diff
                features.pressure_rate_of_change = features.pressure_change_1m / time_diff
                features.humidity_rate_of_change = features.humidity_change_1m / time_diff

        if len(buffer) >= 6:
            readings_5m = list(buffer)[-6:]
            temps = [r.temperature for r in readings_5m]
            pressures = [r.pressure for r in readings_5m]
            humidities = [r.humidity for r in readings_5m]

            features.temp_change_5m = reading.temperature - readings_5m[0].temperature
            features.pressure_change_5m = reading.pressure - readings_5m[0].pressure
            features.humidity_change_5m = reading.humidity - readings_5m[0].humidity

            features.temp_rolling_mean_5 = np.mean(temps[:-1])
            features.temp_rolling_std_5 = np.std(temps[:-1]) if len(temps) > 1 else 0.0
            features.temp_rolling_min_5 = np.min(temps[:-1])
            features.temp_rolling_max_5 = np.max(temps[:-1])

            features.pressure_rolling_mean_5 = np.mean(pressures[:-1])
            features.pressure_rolling_std_5 = np.std(pressures[:-1]) if len(pressures) > 1 else 0.0

            features.humidity_rolling_mean_5 = np.mean(humidities[:-1])
            features.humidity_rolling_std_5 = np.std(humidities[:-1]) if len(humidities) > 1 else 0.0

            if features.temp_rolling_std_5 > 0:
                features.temp_zscore_5 = (reading.temperature - features.temp_rolling_mean_5) / features.temp_rolling_std_5
            if features.pressure_rolling_std_5 > 0:
                features.pressure_zscore_5 = (reading.pressure - features.pressure_rolling_mean_5) / features.pressure_rolling_std_5
            if features.humidity_rolling_std_5 > 0:
                features.humidity_zscore_5 = (reading.humidity - features.humidity_rolling_mean_5) / features.humidity_rolling_std_5

            features.temp_dev_from_ma_5 = reading.temperature - features.temp_rolling_mean_5
            features.pressure_dev_from_ma_5 = reading.pressure - features.pressure_rolling_mean_5
            features.humidity_dev_from_ma_5 = reading.humidity - features.humidity_rolling_mean_5

        if len(buffer) >= 16:
            readings_15m = list(buffer)[-16:]
            temps_15m = [r.temperature for r in readings_15m]
            features.temp_change_15m = reading.temperature - readings_15m[0].temperature

        features.hour_of_day = reading.timestamp.hour
        features.day_of_year = reading.timestamp.timetuple().tm_yday
        features.month = reading.timestamp.month
        features.is_daytime = 1 if 6 <= features.hour_of_day <= 18 else 0

        if features.humidity > 0:
            features.temp_humidity_ratio = features.temperature / features.humidity
        if features.pressure > 0:
            features.temp_pressure_ratio = features.temperature / features.pressure
            features.humidity_pressure_ratio = features.humidity / features.pressure

        features.dew_point = self._calculate_dew_point(features.temperature, features.humidity)
        features.heat_index = self._calculate_heat_index(features.temperature, features.humidity)

        if neighbor_readings:
            neighbor_temps = [r.temperature for r in neighbor_readings.values()]
            neighbor_pressures = [r.pressure for r in neighbor_readings.values()]
            neighbor_humidities = [r.humidity for r in neighbor_readings.values()]

            if neighbor_temps:
                features.station_temp_deviation = features.temperature - np.mean(neighbor_temps)
            if neighbor_pressures:
                features.station_pressure_deviation = features.pressure - np.mean(neighbor_pressures)
            if neighbor_humidities:
                features.station_humidity_deviation = features.humidity - np.mean(neighbor_humidities)

        return features

    def engineer_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.sort_values(["station_id", "timestamp"]).copy()

        feature_rows = []
        for station_id in df["station_id"].unique():
            station_df = df[df["station_id"] == station_id].copy()

            for idx, row in station_df.iterrows():
                reading = WeatherState(
                    temperature=row["temperature"],
                    pressure=row["pressure"],
                    humidity=row["humidity"],
                    timestamp=row["timestamp"]
                )
                features = self.engineer_features(station_id, reading)
                feature_dict = features.to_dict()
                feature_dict["station_id"] = station_id
                feature_dict["timestamp"] = reading.timestamp
                feature_rows.append(feature_dict)

        feature_df = pd.DataFrame(feature_rows)
        return feature_df