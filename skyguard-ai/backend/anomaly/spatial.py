import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque

from backend.config import settings
from backend.simulation.aws_simulator import WeatherState


@dataclass
class SpatialAnomalyResult:
    score: float
    is_anomalous: bool
    neighbor_count: int
    details: Dict[str, Any]


class SpatialConsistencyChecker:
    def __init__(self, max_distance_km: float = 100.0, min_neighbors: int = 2):
        self.max_distance_km = max_distance_km
        self.min_neighbors = min_neighbors
        self.station_buffers: Dict[str, deque] = {}
        self.station_coords = settings.STATION_COORDINATES

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        return R * c

    def _get_nearby_stations(self, station_id: str) -> List[str]:
        if station_id not in self.station_coords:
            return []

        lat1, lon1 = self.station_coords[station_id]
        nearby = []

        for other_id, (lat2, lon2) in self.station_coords.items():
            if other_id == station_id:
                continue
            distance = self._haversine_distance(lat1, lon1, lat2, lon2)
            if distance <= self.max_distance_km:
                nearby.append((other_id, distance))

        nearby.sort(key=lambda x: x[1])
        return [s[0] for s in nearby[:5]]

    def _get_buffer(self, station_id: str) -> deque:
        if station_id not in self.station_buffers:
            self.station_buffers[station_id] = deque(maxlen=20)
        return self.station_buffers[station_id]

    def check_spatial_consistency(
        self,
        station_id: str,
        reading: WeatherState,
        neighbor_readings: Dict[str, WeatherState]
    ) -> SpatialAnomalyResult:
        nearby_stations = self._get_nearby_stations(station_id)
        valid_neighbors = {k: v for k, v in neighbor_readings.items() if k in nearby_stations}

        if len(valid_neighbors) < self.min_neighbors:
            return SpatialAnomalyResult(
                score=0.0,
                is_anomalous=False,
                neighbor_count=len(valid_neighbors),
                details={"reason": "insufficient_neighbors", "neighbors_found": len(valid_neighbors)}
            )

        buffer = self._get_buffer(station_id)
        buffer.append(reading)

        temp_scores = []
        pressure_scores = []
        humidity_scores = []

        for neighbor_id, neighbor_reading in valid_neighbors.items():
            temp_diff = abs(reading.temperature - neighbor_reading.temperature)
            pressure_diff = abs(reading.pressure - neighbor_reading.pressure)
            humidity_diff = abs(reading.humidity - neighbor_reading.humidity)

            temp_scores.append(temp_diff)
            pressure_scores.append(pressure_diff)
            humidity_scores.append(humidity_diff)

        avg_temp_diff = np.mean(temp_scores)
        avg_pressure_diff = np.mean(pressure_scores)
        avg_humidity_diff = np.mean(humidity_scores)

        temp_threshold = 5.0
        pressure_threshold = 5.0
        humidity_threshold = 15.0

        temp_score = min(100.0, (avg_temp_diff / temp_threshold) * 30) if avg_temp_diff > temp_threshold else 0.0
        pressure_score = min(100.0, (avg_pressure_diff / pressure_threshold) * 30) if avg_pressure_diff > pressure_threshold else 0.0
        humidity_score = min(100.0, (avg_humidity_diff / humidity_threshold) * 25) if avg_humidity_diff > humidity_threshold else 0.0

        combined_score = max(temp_score, pressure_score, humidity_score)

        details = {
            "neighbor_count": len(valid_neighbors),
            "neighbor_stations": list(valid_neighbors.keys()),
            "avg_temp_diff": avg_temp_diff,
            "avg_pressure_diff": avg_pressure_diff,
            "avg_humidity_diff": avg_humidity_diff,
            "temp_score": temp_score,
            "pressure_score": pressure_score,
            "humidity_score": humidity_score,
            "max_allowed_temp_diff": temp_threshold,
            "max_allowed_pressure_diff": pressure_threshold,
            "max_allowed_humidity_diff": humidity_threshold
        }

        is_anomalous = combined_score > 50

        return SpatialAnomalyResult(
            score=combined_score,
            is_anomalous=is_anomalous,
            neighbor_count=len(valid_neighbors),
            details=details
        )

    def get_network_health(self, all_readings: Dict[str, WeatherState]) -> Dict[str, Any]:
        station_scores = {}
        for station_id, reading in all_readings.items():
            neighbor_readings = {k: v for k, v in all_readings.items() if k != station_id}
            result = self.check_spatial_consistency(station_id, reading, neighbor_readings)
            station_scores[station_id] = {
                "score": result.score,
                "is_anomalous": result.is_anomalous,
                "neighbor_count": result.neighbor_count
            }

        anomalous_count = sum(1 for s in station_scores.values() if s["is_anomalous"])
        avg_score = np.mean([s["score"] for s in station_scores.values()]) if station_scores else 0.0

        return {
            "network_avg_score": avg_score,
            "anomalous_stations": anomalous_count,
            "total_stations": len(station_scores),
            "station_details": station_scores
        }