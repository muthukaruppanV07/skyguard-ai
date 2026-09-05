import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import random


IMD_STATIONS = [
    {"station_id": "AWS001", "name": "New Delhi", "lat": 28.6139, "lon": 77.2090, "elev": 216, "state": "Delhi"},
    {"station_id": "AWS002", "name": "Mumbai", "lat": 19.0760, "lon": 72.8777, "elev": 14, "state": "Maharashtra"},
    {"station_id": "AWS003", "name": "Bangalore", "lat": 12.9716, "lon": 77.5946, "elev": 920, "state": "Karnataka"},
    {"station_id": "AWS004", "name": "Chennai", "lat": 13.0827, "lon": 80.2707, "elev": 6, "state": "Tamil Nadu"},
    {"station_id": "AWS005", "name": "Kolkata", "lat": 22.5726, "lon": 88.3639, "elev": 9, "state": "West Bengal"},
    {"station_id": "AWS006", "name": "Hyderabad", "lat": 17.3850, "lon": 78.4867, "elev": 505, "state": "Telangana"},
    {"station_id": "AWS007", "name": "Pune", "lat": 18.5204, "lon": 73.8567, "elev": 560, "state": "Maharashtra"},
    {"station_id": "AWS008", "name": "Ahmedabad", "lat": 23.0225, "lon": 72.5714, "elev": 53, "state": "Gujarat"},
    {"station_id": "AWS009", "name": "Jaipur", "lat": 26.9124, "lon": 75.7873, "elev": 431, "state": "Rajasthan"},
    {"station_id": "AWS010", "name": "Lucknow", "lat": 26.8467, "lon": 80.9462, "elev": 123, "state": "Uttar Pradesh"},
    {"station_id": "AWS011", "name": "Bhopal", "lat": 23.2599, "lon": 77.4126, "elev": 497, "state": "Madhya Pradesh"},
    {"station_id": "AWS012", "name": "Patna", "lat": 25.5941, "lon": 85.1376, "elev": 53, "state": "Bihar"},
    {"station_id": "AWS013", "name": "Guwahati", "lat": 26.1445, "lon": 91.7362, "elev": 55, "state": "Assam"},
    {"station_id": "AWS014", "name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245, "elev": 45, "state": "Odisha"},
    {"station_id": "AWS015", "name": "Thiruvananthapuram", "lat": 8.5241, "lon": 76.9366, "elev": 64, "state": "Kerala"},
]


MONTHLY_CLIMATOLOGY = {
    1: {"temp_base": 20, "pressure_base": 1015, "humidity_base": 55, "temp_range": 8},
    2: {"temp_base": 22, "pressure_base": 1014, "humidity_base": 50, "temp_range": 9},
    3: {"temp_base": 27, "pressure_base": 1012, "humidity_base": 45, "temp_range": 10},
    4: {"temp_base": 32, "pressure_base": 1010, "humidity_base": 50, "temp_range": 10},
    5: {"temp_base": 35, "pressure_base": 1008, "humidity_base": 60, "temp_range": 9},
    6: {"temp_base": 33, "pressure_base": 1006, "humidity_base": 75, "temp_range": 7},
    7: {"temp_base": 30, "pressure_base": 1005, "humidity_base": 85, "temp_range": 5},
    8: {"temp_base": 29, "pressure_base": 1006, "humidity_base": 85, "temp_range": 5},
    9: {"temp_base": 29, "pressure_base": 1008, "humidity_base": 80, "temp_range": 6},
    10: {"temp_base": 28, "pressure_base": 1011, "humidity_base": 70, "temp_range": 7},
    11: {"temp_base": 24, "pressure_base": 1013, "humidity_base": 60, "temp_range": 8},
    12: {"temp_base": 21, "pressure_base": 1014, "humidity_base": 55, "temp_range": 8},
}


def get_solar_elevation(dt: datetime, lat: float) -> float:
    day_of_year = dt.timetuple().tm_yday
    hour = dt.hour + dt.minute / 60.0
    
    declination = -23.44 * np.cos(2 * np.pi * (day_of_year + 10) / 365)
    declination_rad = np.radians(declination)
    lat_rad = np.radians(lat)
    
    hour_angle = np.radians(15 * (hour - 12))
    
    sin_elev = (
        np.sin(lat_rad) * np.sin(declination_rad)
        + np.cos(lat_rad) * np.cos(declination_rad) * np.cos(hour_angle)
    )
    elevation = np.degrees(np.asin(np.clip(sin_elev, -1, 1)))
    return max(0, elevation)


def generate_realistic_reading(station: Dict, dt: datetime, prev_reading: Optional[Dict] = None) -> Dict:
    month = dt.month
    clim = MONTHLY_CLIMATOLOGY[month]
    
    lat = station["lat"]
    elev = station["elev"]
    
    base_temp = clim["temp_base"] - (elev / 1000) * 6.5
    base_pressure = clim["pressure_base"] - elev * 0.12
    base_humidity = clim["humidity_base"]
    
    solar_elev = get_solar_elevation(dt, station["lat"])
    hour = dt.hour + dt.minute / 60.0
    
    temp_cycle = clim["temp_range"] * np.sin(2 * np.pi * (hour - 6) / 24)
    temp_cycle = max(0, temp_cycle) * (solar_elev / 90.0) if solar_elev > 0 else temp_cycle * 0.3
    
    pressure_cycle = 1.5 * np.sin(2 * np.pi * hour / 12)
    humidity_cycle = -clim["temp_range"] * 0.8 * np.sin(2 * np.pi * (hour - 6) / 24)
    
    expected_temp = base_temp + temp_cycle
    expected_pressure = base_pressure + pressure_cycle
    expected_humidity = np.clip(base_humidity + humidity_cycle, 5, 100)
    
    temp_noise = random.gauss(0, 0.2)
    pressure_noise = random.gauss(0, 0.1)
    humidity_noise = random.gauss(0, 0.5)
    
    temperature = expected_temp + temp_noise
    pressure = expected_pressure + pressure_noise
    humidity = np.clip(expected_humidity + humidity_noise, 0, 100)
    
    if prev_reading:
        max_temp_change = 2.0
        max_pressure_change = 5.0
        max_humidity_change = 5.0
        
        dt_diff = (dt - prev_reading["timestamp"]).total_seconds() / 60
        if dt_diff > 0:
            temperature = np.clip(
                temperature,
                prev_reading["temperature"] - max_temp_change * dt_diff,
                prev_reading["temperature"] + max_temp_change * dt_diff
            )
            pressure = np.clip(
                pressure,
                prev_reading["pressure"] - max_pressure_change * dt_diff,
                prev_reading["pressure"] + max_pressure_change * dt_diff
            )
            humidity = np.clip(
                humidity,
                prev_reading["humidity"] - max_humidity_change * dt_diff,
                prev_reading["humidity"] + max_humidity_change * dt_diff
            )
    
    return {
        "station_id": station["station_id"],
        "station_name": station["name"],
        "latitude": station["lat"],
        "longitude": station["lon"],
        "elevation": station["elev"],
        "state": station["state"],
        "timestamp": dt,
        "temperature": round(temperature, 2),
        "pressure": round(pressure, 2),
        "humidity": round(humidity, 2),
        "quality_flag": "good"
    }


def generate_imd_dataset(
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    interval_minutes: int = 60,
    stations: List[Dict] = None,
    output_path: str = None
) -> pd.DataFrame:
    stations = stations or IMD_STATIONS
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    
    all_readings = []
    current = start
    
    station_last_reading = {s["station_id"]: None for s in stations}
    
    total_steps = int((end - start).total_seconds() / (interval_minutes * 60))
    print(f"Generating {total_steps} time steps for {len(stations)} stations...")
    
    step = 0
    current = start
    while current <= end:
        for station in stations:
            prev = station_last_reading[station["station_id"]]
            reading = generate_realistic_reading(station, current, prev)
            all_readings.append(reading)
            station_last_reading[station["station_id"]] = reading
        
        current += timedelta(minutes=interval_minutes)
        step += 1
        if step % 10000 == 0:
            print(f"Progress: {step}/{total_steps} steps")
    
    df = pd.DataFrame(all_readings)
    
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Saved to {output_path}")
    
    print(f"Generated {len(df)} readings from {len(stations)} stations")
    return df


def add_realistic_anomalies(df: pd.DataFrame, anomaly_rate: float = 0.01) -> pd.DataFrame:
    df = df.copy()
    n_anomalies = int(len(df) * anomaly_rate)
    anomaly_indices = np.random.choice(len(df), n_anomalies, replace=False)
    
    for idx in anomaly_indices:
        anomaly_type = np.random.choice([
            "temperature_spike", "pressure_spike", "humidity_spike",
            "sensor_drift", "frozen_sensor", "missing_data"
        ])
        
        if anomaly_type == "temperature_spike":
            df.loc[idx, "temperature"] += np.random.uniform(10, 20)
            df.loc[idx, "quality_flag"] = "temperature_spike"
        elif anomaly_type == "pressure_spike":
            df.loc[idx, "pressure"] += np.random.uniform(15, 30)
            df.loc[idx, "quality_flag"] = "pressure_spike"
        elif anomaly_type == "humidity_spike":
            df.loc[idx, "humidity"] = np.clip(
                df.loc[idx, "humidity"] + np.random.uniform(-30, 30), 0, 100
            )
            df.loc[idx, "quality_flag"] = "humidity_spike"
        elif anomaly_type == "sensor_drift":
            pass
        elif anomaly_type == "frozen_sensor":
            df.loc[idx, "quality_flag"] = "frozen_sensor"
        elif anomaly_type == "missing_data":
            df.loc[idx, "quality_flag"] = "missing_data"
    
    return df


def generate_imd_sample_csv(
    output_dir: str = "data/sample",
    start_date: str = "2024-06-01",
    end_date: str = "2024-06-30",
    interval_minutes: int = 60
) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    output_file = Path(output_dir) / f"imd_sample_{start_date}_to_{end_date}.csv"
    
    df = generate_imd_dataset(
        start_date=start_date,
        end_date=end_date,
        interval_minutes=interval_minutes
    )
    
    df_with_anomalies = add_realistic_anomalies(df, anomaly_rate=0.005)
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    df_with_anomalies.to_csv(output_file, index=False)
    
    print(f"Generated IMD sample data: {output_file}")
    print(f"  Stations: 15")
    print(f"  Period: {start_date} to {end_date}")
    print(f"  Interval: {interval_minutes} minutes")
    print(f"  Records: {len(df_with_anomalies)}")
    print(f"  Anomalies injected: ~{len(df_with_anomalies) * 0.005:.0f}")
    
    return str(output_file)


def generate_monsoon_period_data() -> pd.DataFrame:
    return generate_imd_dataset(
        start_date="2024-06-01",
        end_date="2024-09-30",
        interval_minutes=30
    )


def generate_heatwave_period_data() -> pd.DataFrame:
    df = generate_imd_dataset(
        start_date="2024-04-01",
        end_date="2024-06-15",
        interval_minutes=60
    )
    
    heatwave_indices = df[
        (df["timestamp"].dt.month.isin([4, 5, 6])) &
        (df["temperature"] > 40)
    ].index
    
    for idx in heatwave_indices:
        df.loc[idx, "quality_flag"] = "heatwave"
    
    return df


def generate_cyclone_period_data() -> pd.DataFrame:
    df = generate_imd_dataset(
        start_date="2024-10-01",
        end_date="2024-11-30",
        interval_minutes=30
    )
    
    cyclone_indices = df[
        (df["pressure"] < 1000) &
        (df["timestamp"].dt.month.isin([10, 11]))
    ].index
    
    for idx in cyclone_indices:
        df.loc[idx, "quality_flag"] = "cyclone_approach"
    
    return df


if __name__ == "__main__":
    print("Generating IMD sample data for SIH demo...")
    
    output_dir = "data/imd_sample"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print("\n1. Generating June 2024 sample (hourly)...")
    generate_imd_sample_csv(
        output_dir="data/imd_sample",
        start_date="2024-06-01",
        end_date="2024-06-30",
        interval_minutes=60
    )
    
    print("\n2. Generating monsoon period (Jun-Sep, 30-min)...")
    monsoon_df = generate_monsoon_period_data()
    monsoon_df.to_csv("data/imd_sample/monsoon_2024.csv", index=False)
    print(f"  Saved monsoon data: {len(monsoon_df)} records")
    
    print("\n3. Generating heatwave period (Apr-Jun)...")
    heatwave_df = generate_heatwave_period_data()
    heatwave_df.to_csv("data/imd_sample/heatwave_2024.csv", index=False)
    print(f"  Saved heatwave data: {len(heatwave_df)} records")
    
    print("\n4. Generating cyclone period (Oct-Nov)...")
    cyclone_df = generate_cyclone_period_data()
    cyclone_df.to_csv("data/imd_sample/cyclone_2024.csv", index=False)
    print(f"  Saved cyclone data: {len(cyclone_df)} records")
    
    print("\nAll IMD sample data generated!")
    print(f"Files saved to: data/imd_sample/")