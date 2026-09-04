import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import random
import math

from backend.config import settings


@dataclass
class WeatherState:
    temperature: float
    pressure: float
    humidity: float
    timestamp: datetime


class AWSSimulator:
    def __init__(self, station_id: str, seed: Optional[int] = None):
        self.station_id = station_id
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

        self.base_temp = 25.0 + np.random.uniform(-5, 5)
        self.base_pressure = 1013.25 + np.random.uniform(-10, 10)
        self.base_humidity = 60.0 + np.random.uniform(-20, 20)

        self.temp_trend = 0.0
        self.pressure_trend = 0.0
        self.humidity_trend = 0.0

        self.last_state: Optional[WeatherState] = None
        self.history: List[WeatherState] = []
        self.max_history = 10000

    def _daily_temperature_cycle(self, hour: float, day_of_year: int) -> float:
        daily_amplitude = 8.0 + 4.0 * np.sin(2 * np.pi * (day_of_year - 172) / 365)
        seasonal_offset = 5.0 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
        hourly_cycle = -daily_amplitude * np.cos(2 * np.pi * (hour - 6) / 24)
        return hourly_cycle + seasonal_offset

    def _pressure_variation(self, hour: float, day_of_year: int) -> float:
        diurnal = 1.5 * np.cos(2 * np.pi * (hour - 10) / 24)
        semi_diurnal = 0.8 * np.cos(4 * np.pi * (hour - 10) / 24)
        seasonal = 2.0 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
        return diurnal + semi_diurnal + seasonal

    def _humidity_from_temp(self, temperature: float, base_humidity: float) -> float:
        dew_point = temperature - (100 - base_humidity) / 5.0
        if temperature <= dew_point:
            return 100.0
        rh = 100.0 * (np.exp((17.625 * dew_point) / (243.04 + dew_point)) /
                      np.exp((17.625 * temperature) / (243.04 + temperature)))
        return np.clip(rh + np.random.normal(0, 3), 10, 100)

    def _add_noise(self, value: float, noise_std: float) -> float:
        return value + np.random.normal(0, noise_std)

    def generate_reading(self, timestamp: Optional[datetime] = None) -> WeatherState:
        if timestamp is None:
            timestamp = datetime.utcnow()

        hour = timestamp.hour + timestamp.minute / 60.0 + timestamp.second / 3600.0
        day_of_year = timestamp.timetuple().tm_yday

        temp_cycle = self._daily_temperature_cycle(hour, day_of_year)
        pressure_cycle = self._pressure_variation(hour, day_of_year)

        self.temp_trend += np.random.normal(0, 0.05)
        self.pressure_trend += np.random.normal(0, 0.02)
        self.humidity_trend += np.random.normal(0, 0.1)

        self.temp_trend *= 0.99
        self.pressure_trend *= 0.99
        self.humidity_trend *= 0.99

        temperature = self.base_temp + temp_cycle + self.temp_trend
        pressure = self.base_pressure + pressure_cycle + self.pressure_trend
        humidity = self._humidity_from_temp(temperature, self.base_humidity + self.humidity_trend)

        temperature = self._add_noise(temperature, 0.2)
        pressure = self._add_noise(pressure, 0.15)
        humidity = self._add_noise(humidity, 1.0)

        temperature = np.clip(temperature, -10, 50)
        pressure = np.clip(pressure, 900, 1100)
        humidity = np.clip(humidity, 0, 100)

        state = WeatherState(
            temperature=round(temperature, 2),
            pressure=round(pressure, 2),
            humidity=round(humidity, 2),
            timestamp=timestamp
        )

        self.last_state = state
        self.history.append(state)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        return state

    def generate_batch(self, start_time: datetime, count: int, interval_minutes: int = 5) -> List[WeatherState]:
        readings = []
        current_time = start_time
        for _ in range(count):
            readings.append(self.generate_reading(current_time))
            current_time += timedelta(minutes=interval_minutes)
        return readings


class MultiStationSimulator:
    def __init__(self, station_ids: List[str], seed: Optional[int] = None):
        self.station_ids = station_ids
        self.simulators: Dict[str, AWSSimulator] = {}
        for i, sid in enumerate(station_ids):
            sim_seed = seed + i if seed is not None else None
            self.simulators[sid] = AWSSimulator(sid, sim_seed)

    def generate_all(self, timestamp: Optional[datetime] = None) -> Dict[str, WeatherState]:
        return {sid: sim.generate_reading(timestamp) for sid, sim in self.simulators.items()}

    def generate_batch_all(self, start_time: datetime, count: int, interval_minutes: int = 5) -> Dict[str, List[WeatherState]]:
        return {sid: sim.generate_batch(start_time, count, interval_minutes) for sid, sim in self.simulators.items()}

    def get_station_history(self, station_id: str, limit: int = 100) -> List[WeatherState]:
        if station_id in self.simulators:
            return self.simulators[station_id].history[-limit:]
        return []


def create_historical_data(days: int = 30, interval_minutes: int = 5) -> pd.DataFrame:
    simulator = MultiStationSimulator(settings.STATION_IDS, seed=42)
    end_time = datetime.utcnow().replace(second=0, microsecond=0)
    start_time = end_time - timedelta(days=days)

    all_readings = []
    for station_id in settings.STATION_IDS:
        readings = simulator.simulators[station_id].generate_batch(start_time, int(days * 24 * 60 / interval_minutes), interval_minutes)
        for r in readings:
            all_readings.append({
                "station_id": station_id,
                "timestamp": r.timestamp,
                "temperature": r.temperature,
                "pressure": r.pressure,
                "humidity": r.humidity
            })

    df = pd.DataFrame(all_readings)
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    return df