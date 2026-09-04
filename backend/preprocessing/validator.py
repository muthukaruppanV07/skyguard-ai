import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from backend.config import settings


class DataValidator:
    def __init__(self):
        self.temp_min = settings.TEMP_MIN
        self.temp_max = settings.TEMP_MAX
        self.pressure_min = settings.PRESSURE_MIN
        self.pressure_max = settings.PRESSURE_MAX
        self.humidity_min = settings.HUMIDITY_MIN
        self.humidity_max = settings.HUMIDITY_MAX
        self.max_temp_change = settings.MAX_TEMP_CHANGE_PER_MIN
        self.max_pressure_change = settings.MAX_PRESSURE_CHANGE_PER_MIN
        self.max_humidity_change = settings.MAX_HUMIDITY_CHANGE_PER_MIN
        self.frozen_threshold = settings.FROZEN_THRESHOLD_MINUTES
        self.missing_threshold = settings.MISSING_THRESHOLD_MINUTES

    def validate_reading(
        self,
        station_id: str,
        timestamp: datetime,
        temperature: float,
        pressure: float,
        humidity: float,
        previous_readings: List[Dict] = None,
    ) -> Dict[str, Any]:
        issues = []
        warnings = []

        if temperature < self.temp_min or temperature > self.temp_max:
            issues.append(f"Temperature {temperature}°C outside plausible range [{self.temp_min}, {self.temp_max}]")

        if pressure < self.pressure_min or pressure > self.pressure_max:
            issues.append(f"Pressure {pressure} hPa outside plausible range [{self.pressure_min}, {self.pressure_max}]")

        if humidity < self.humidity_min or humidity > self.humidity_max:
            issues.append(f"Humidity {humidity}% outside plausible range [{self.humidity_min}, {self.humidity_max}]")

        if previous_readings:
            prev = previous_readings[-1] if previous_readings else None
            if prev:
                time_diff = (timestamp - prev["timestamp"]).total_seconds() / 60
                if time_diff > 0:
                    temp_change = abs(temperature - prev["temperature"]) / time_diff
                    pressure_change = abs(pressure - prev["pressure"]) / time_diff
                    humidity_change = abs(humidity - prev["humidity"]) / time_diff

                    if temp_change > self.max_temp_change:
                        issues.append(f"Temperature change rate {temp_change:.2f}°C/min exceeds max {self.max_temp_change}°C/min")
                    if pressure_change > self.max_pressure_change:
                        issues.append(f"Pressure change rate {pressure_change:.2f} hPa/min exceeds max {self.max_pressure_change} hPa/min")
                    if humidity_change > self.max_humidity_change:
                        issues.append(f"Humidity change rate {humidity_change:.2f}%/min exceeds max {self.max_humidity_change}%/min")

            if len(previous_readings) >= self.frozen_threshold:
                recent = previous_readings[-self.frozen_threshold:]
                temp_std = np.std([r["temperature"] for r in recent])
                pressure_std = np.std([r["pressure"] for r in recent])
                humidity_std = np.std([r["humidity"] for r in recent])
                
                if temp_std < 0.01:
                    issues.append(f"Temperature frozen (std={temp_std:.4f}) for {self.frozen_threshold} minutes")
                if pressure_std < 0.01:
                    issues.append(f"Pressure frozen (std={pressure_std:.4f}) for {self.frozen_threshold} minutes")
                if humidity_std < 0.01:
                    issues.append(f"Humidity frozen (std={humidity_std:.4f}) for {self.frozen_threshold} minutes")

        is_valid = len(issues) == 0

        return {
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "score": 0.0 if is_valid else 1.0,
        }

    def validate_batch(self, readings: List[Dict]) -> List[Dict]:
        results = []
        for i, reading in enumerate(readings):
            prev = readings[max(0, i-10):i] if i > 0 else []
            result = self.validate_reading(
                station_id=reading["station_id"],
                timestamp=reading["timestamp"],
                temperature=reading["temperature"],
                pressure=reading["pressure"],
                humidity=reading["humidity"],
                previous_readings=prev,
            )
            result["index"] = i
            results.append(result)
        return results

    def check_duplicates(self, readings: List[Dict]) -> List[int]:
        seen = {}
        duplicates = []
        for i, r in enumerate(readings):
            key = (r["station_id"], r["timestamp"])
            if key in seen:
                duplicates.append(i)
            else:
                seen[key] = i
        return duplicates

    def check_gaps(self, readings: List[Dict], expected_interval_minutes: int = 1) -> List[Dict]:
        gaps = []
        if len(readings) < 2:
            return gaps
        
        sorted_readings = sorted(readings, key=lambda x: x["timestamp"])
        for i in range(1, len(sorted_readings)):
            prev = sorted_readings[i-1]
            curr = sorted_readings[i]
            if prev["station_id"] == curr["station_id"]:
                expected = prev["timestamp"] + timedelta(minutes=expected_interval_minutes)
                actual_diff = (curr["timestamp"] - prev["timestamp"]).total_seconds() / 60
                if actual_diff > expected_interval_minutes * 1.5:
                    gaps.append({
                        "station_id": prev["station_id"],
                        "gap_start": prev["timestamp"],
                        "gap_end": curr["timestamp"],
                        "missing_minutes": actual_diff - expected_interval_minutes,
                    })
        return gaps

    def compute_validation_score(self, validation_result: Dict) -> float:
        if validation_result["is_valid"]:
            return 0.0
        
        issue_count = len(validation_result["issues"])
        return min(1.0, issue_count * 0.2)


def create_validator() -> DataValidator:
    return DataValidator()