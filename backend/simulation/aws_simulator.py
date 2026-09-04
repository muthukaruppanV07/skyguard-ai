import asyncio
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.config import settings
from backend.models import Station, Reading
from backend.database.session import AsyncSessionLocal


class AWSSimulator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stations: Dict[str, dict] = {}
        self.running = False
        self._init_station_states()

    def _init_station_states(self):
        for station_config in settings.STATION_COORDS:
            station_id = station_config["station_id"]
            lat = station_config["latitude"]
            lon = station_config["longitude"]
            elev = station_config["elevation"]

            base_temp = 25.0 - (elev / 1000.0) * 6.5 - abs(lat - 20) * 0.3
            base_pressure = 1013.25 - elev * 0.12
            base_humidity = 60.0 + (lat - 20) * 0.5 + random.uniform(-10, 10)

            self.stations[station_id] = {
                "config": station_config,
                "base_temp": base_temp,
                "base_pressure": base_pressure,
                "base_humidity": max(20, min(90, base_humidity)),
                "last_temp": base_temp,
                "last_pressure": base_pressure,
                "last_humidity": base_humidity,
                "last_timestamp": None,
                "frozen_until": None,
                "frozen_values": None,
                "drift_temp": 0.0,
                "drift_pressure": 0.0,
                "drift_humidity": 0.0,
                "comm_failure_until": None,
                "degradation_factor": 1.0,
            }

    async def reset(self):
        self._init_station_states()

    def _get_solar_elevation(self, timestamp: datetime, lat: float) -> float:
        day_of_year = timestamp.timetuple().tm_yday
        hour = timestamp.hour + timestamp.minute / 60.0

        declination = -23.44 * math.cos(2 * math.pi * (day_of_year + 10) / 365)
        declination_rad = math.radians(declination)
        lat_rad = math.radians(lat)

        hour_angle = math.radians(15 * (hour - 12))

        sin_elev = (
            math.sin(lat_rad) * math.sin(declination_rad)
            + math.cos(lat_rad) * math.cos(declination_rad) * math.cos(hour_angle)
        )
        elevation = math.degrees(math.asin(max(-1, min(1, sin_elev))))
        return max(0, elevation)

    def _calculate_expected_values(self, station_id: str, timestamp: datetime) -> tuple:
        state = self.stations[station_id]
        lat = state["config"]["latitude"]

        solar_elev = self._get_solar_elevation(timestamp, lat)
        hour = timestamp.hour + timestamp.minute / 60.0

        temp_cycle = 8.0 * math.sin(2 * math.pi * (hour - 6) / 24)
        temp_cycle = max(0, temp_cycle) * (solar_elev / 90.0) if solar_elev > 0 else temp_cycle * 0.3

        expected_temp = state["base_temp"] + temp_cycle + state["drift_temp"]

        pressure_cycle = 1.5 * math.sin(2 * math.pi * hour / 12)
        expected_pressure = state["base_pressure"] + pressure_cycle + state["drift_pressure"]

        humidity_cycle = -10.0 * math.sin(2 * math.pi * (hour - 6) / 24)
        humidity_cycle = max(-15, humidity_cycle) if solar_elev > 0 else humidity_cycle * 0.5
        expected_humidity = state["base_humidity"] + humidity_cycle + state["drift_humidity"]

        expected_humidity = max(5, min(100, expected_humidity))

        return expected_temp, expected_pressure, expected_humidity

    def _add_realistic_noise(self, temp: float, pressure: float, humidity: float, state: dict) -> tuple:
        degradation = state["degradation_factor"]
        
        temp_noise = random.gauss(0, 0.15 * degradation)
        pressure_noise = random.gauss(0, 0.08 * degradation)
        humidity_noise = random.gauss(0, 0.5 * degradation)

        temp = temp + temp_noise
        pressure = pressure + pressure_noise
        humidity = humidity + humidity_noise

        humidity = max(0, min(100, humidity))

        if state["last_temp"] is not None:
            max_temp_change = settings.MAX_TEMP_CHANGE_PER_MIN
            temp = max(state["last_temp"] - max_temp_change, min(state["last_temp"] + max_temp_change, temp))
            
            max_pressure_change = settings.MAX_PRESSURE_CHANGE_PER_MIN
            pressure = max(state["last_pressure"] - max_pressure_change, min(state["last_pressure"] + max_pressure_change, pressure))
            
            max_humidity_change = settings.MAX_HUMIDITY_CHANGE_PER_MIN
            humidity = max(state["last_humidity"] - max_humidity_change, min(state["last_humidity"] + max_humidity_change, humidity))

        return temp, pressure, humidity

    async def generate_reading(self, station_id: str, timestamp: datetime) -> Optional[Reading]:
        state = self.stations[station_id]

        if state["comm_failure_until"] and timestamp < state["comm_failure_until"]:
            return None

        if state["frozen_until"] and timestamp < state["frozen_until"]:
            if state["frozen_values"]:
                return Reading(
                    station_id=station_id,
                    timestamp=timestamp,
                    temperature=state["frozen_values"][0],
                    pressure=state["frozen_values"][1],
                    humidity=state["frozen_values"][2],
                    is_valid=True,
                )
            return None

        expected_temp, expected_pressure, expected_humidity = self._calculate_expected_values(station_id, timestamp)
        temp, pressure, humidity = self._add_realistic_noise(expected_temp, expected_pressure, expected_humidity, state)

        state["last_temp"] = temp
        state["last_pressure"] = pressure
        state["last_humidity"] = humidity
        state["last_timestamp"] = timestamp

        return Reading(
            station_id=station_id,
            timestamp=timestamp,
            temperature=round(temp, 2),
            pressure=round(pressure, 2),
            humidity=round(humidity, 2),
            is_valid=True,
        )

    async def generate_all_readings(self, timestamp: datetime) -> List[Reading]:
        readings = []
        for station_id in self.stations:
            reading = await self.generate_reading(station_id, timestamp)
            if reading:
                readings.append(reading)
        return readings

    async def run_simulation_step(self, timestamp: datetime):
        readings = await self.generate_all_readings(timestamp)
        for reading in readings:
            self.db.add(reading)
        await self.db.commit()
        return readings

    async def start_continuous(self, interval_seconds: int = 1):
        self.running = True
        current_time = datetime.utcnow().replace(second=0, microsecond=0)
        
        while self.running:
            await self.run_simulation_step(current_time)
            current_time += timedelta(seconds=interval_seconds)
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self.running = False

    def apply_drift(self, station_id: str, temp_drift: float = 0, pressure_drift: float = 0, humidity_drift: float = 0):
        if station_id in self.stations:
            self.stations[station_id]["drift_temp"] += temp_drift
            self.stations[station_id]["drift_pressure"] += pressure_drift
            self.stations[station_id]["drift_humidity"] += humidity_drift

    def freeze_sensor(self, station_id: str, duration_minutes: int = 30):
        if station_id in self.stations:
            state = self.stations[station_id]
            state["frozen_until"] = datetime.utcnow() + timedelta(minutes=duration_minutes)
            state["frozen_values"] = (state["last_temp"], state["last_pressure"], state["last_humidity"])

    def unfreeze_sensor(self, station_id: str):
        if station_id in self.stations:
            self.stations[station_id]["frozen_until"] = None
            self.stations[station_id]["frozen_values"] = None

    def set_comm_failure(self, station_id: str, duration_minutes: int = 10):
        if station_id in self.stations:
            self.stations[station_id]["comm_failure_until"] = datetime.utcnow() + timedelta(minutes=duration_minutes)

    def clear_comm_failure(self, station_id: str):
        if station_id in self.stations:
            self.stations[station_id]["comm_failure_until"] = None

    def set_degradation(self, station_id: str, factor: float):
        if station_id in self.stations:
            self.stations[station_id]["degradation_factor"] = max(1.0, factor)


async def run_historical_simulation(days: int = 30, interval_minutes: int = 5):
    async with AsyncSessionLocal() as db:
        simulator = AWSSimulator(db)
        
        start_time = datetime.utcnow() - timedelta(days=days)
        current_time = start_time.replace(second=0, microsecond=0)
        end_time = datetime.utcnow()
        
        total_steps = int((end_time - start_time).total_seconds() / (interval_minutes * 60))
        print(f"Generating {total_steps} time steps for {len(settings.STATION_COORDS)} stations...")
        
        step = 0
        while current_time <= end_time:
            await simulator.run_simulation_step(current_time)
            current_time += timedelta(minutes=interval_minutes)
            step += 1
            if step % 1000 == 0:
                print(f"Progress: {step}/{total_steps} steps")
        
        print("Historical simulation complete!")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "historical":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        asyncio.run(run_historical_simulation(days))
    else:
        print("Usage: python -m backend.simulation.aws_simulator historical [days]")