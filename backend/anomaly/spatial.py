import numpy as np
import pandas as pd
from typing import List, Dict, Any
from backend.config import settings
from backend.utils.math import haversine_distance


class SpatialAnalyzer:
    def __init__(
        self,
        k_neighbors: int = settings.SPATIAL_K_NEIGHBORS,
        max_distance_km: float = settings.SPATIAL_MAX_DISTANCE_KM,
        weight_decay: float = settings.SPATIAL_WEIGHT_DECAY,
        threshold: float = settings.SPATIAL_THRESHOLD,
    ):
        self.k_neighbors = k_neighbors
        self.max_distance_km = max_distance_km
        self.weight_decay = weight_decay
        self.threshold = threshold

    def analyze(
        self,
        station_id: str,
        current: Dict,
        neighbor_readings: Dict[str, List[Dict]],
        station_coords: Dict[str, Dict],
    ) -> Dict[str, Any]:
        if not neighbor_readings or station_id not in station_coords:
            return self._default_result()

        neighbors = self._get_nearest_neighbors(station_id, station_coords)
        if not neighbors:
            return self._default_result()

        scores = {}
        for param in ["temperature", "pressure", "humidity"]:
            scores[param] = self._compute_spatial_deviation(
                station_id, current[param], neighbor_readings, neighbors, param
            )

        overall = np.mean(list(scores.values()))

        return {
            "spatial_score": round(min(100, overall * 100), 2),
            "components": {k: round(v * 100, 2) for k, v in scores.items()},
            "details": {
                "neighbors_used": neighbors,
                "neighbor_values": {
                    n_id: {
                        param: np.mean([r[param] for r in readings[-5:]]) if readings else 0
                        for param in ["temperature", "pressure", "humidity"]
                    }
                    for n_id, readings in neighbor_readings.items()
                    if n_id in neighbors
                },
            },
        }

    def _get_nearest_neighbors(
        self,
        station_id: str,
        station_coords: Dict[str, Dict],
    ) -> List[str]:
        if station_id not in station_coords:
            return []

        target_lat = station_coords[station_id]["latitude"]
        target_lon = station_coords[station_id]["longitude"]

        distances = []
        for other_id, coords in station_coords.items():
            if other_id == station_id:
                continue
            dist = haversine_distance(target_lat, target_lon, coords["latitude"], coords["longitude"])
            if dist <= self.max_distance_km:
                distances.append((other_id, dist))

        distances.sort(key=lambda x: x[1])
        return [n[0] for n in distances[:self.k_neighbors]]

    def _compute_spatial_deviation(
        self,
        station_id: str,
        current_value: float,
        neighbor_readings: Dict[str, List[Dict]],
        neighbors: List[str],
        parameter: str,
    ) -> float:
        if not neighbors:
            return 0.0

        weighted_sum = 0.0
        weight_sum = 0.0

        for neighbor_id in neighbors:
            readings = neighbor_readings.get(neighbor_id, [])
            if not readings:
                continue

            recent_values = [r[parameter] for r in readings[-5:]]
            if not recent_values:
                continue

            neighbor_mean = np.mean(recent_values)
            neighbor_std = np.std(recent_values)

            from backend.utils.math import haversine_distance
            from backend.config import settings
            station_coords = settings.STATION_COORDS
            target = next(s for s in station_coords if s["station_id"] == station_id)
            neighbor = next(s for s in station_coords if s["station_id"] == neighbor_id)
            dist = haversine_distance(
                target["latitude"], target["longitude"],
                neighbor["latitude"], neighbor["longitude"]
            )

            weight = np.exp(-dist / self.weight_decay)
            
            if neighbor_std > 0:
                zscore = abs(current_value - neighbor_mean) / neighbor_std
                deviation = min(1.0, zscore / self.threshold)
            else:
                deviation = 1.0 if abs(current_value - neighbor_mean) > 1 else 0.0

            weighted_sum += weight * deviation
            weight_sum += weight

        if weight_sum > 0:
            return weighted_sum / weight_sum
        return 0.0

    def _default_result(self) -> Dict:
        return {
            "spatial_score": 0.0,
            "components": {
                "temperature": 0.0,
                "pressure": 0.0,
                "humidity": 0.0,
            },
            "details": {},
        }


def create_spatial_analyzer() -> SpatialAnalyzer:
    return SpatialAnalyzer()