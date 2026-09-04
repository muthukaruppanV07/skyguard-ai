export const SEVERITY_LEVELS = [
  { value: 'NORMAL', label: 'Normal', color: '#22c55e', range: '0-30' },
  { value: 'LOW', label: 'Low', color: '#84cc16', range: '30-50' },
  { value: 'SUSPICIOUS', label: 'Suspicious', color: '#facc15', range: '50-70' },
  { value: 'HIGH', label: 'High', color: '#f97316', range: '70-85' },
  { value: 'CRITICAL', label: 'Critical', color: '#ef4444', range: '85-100' },
]

export const ROOT_CAUSE_LABELS = {
  NORMAL: 'Normal',
  TEMPERATURE_SPIKE: 'Temperature Spike',
  PRESSURE_SPIKE: 'Pressure Spike',
  HUMIDITY_SPIKE: 'Humidity Spike',
  SENSOR_DRIFT: 'Sensor Drift',
  FROZEN_SENSOR: 'Frozen Sensor',
  MISSING_DATA: 'Missing Data',
  DUPLICATE_DATA: 'Duplicate Data',
  COMMUNICATION_FAILURE: 'Communication Failure',
  MULTIVARIATE_INCONSISTENCY: 'Multivariate Inconsistency',
  POSSIBLE_SENSOR_MALFUNCTION: 'Possible Sensor Malfunction',
  POSSIBLE_REAL_WEATHER_EVENT: 'Possible Real Weather Event',
}

export const ANOMALY_INJECTION_TYPES = [
  { value: 'TEMPERATURE_SPIKE', label: 'Inject Temperature Spike', description: 'Sudden temperature increase' },
  { value: 'PRESSURE_SPIKE', label: 'Inject Pressure Spike', description: 'Sudden pressure increase' },
  { value: 'HUMIDITY_SPIKE', label: 'Inject Humidity Spike', description: 'Sudden humidity change' },
  { value: 'TEMPERATURE_DRIFT', label: 'Inject Temperature Drift', description: 'Gradual temperature drift' },
  { value: 'PRESSURE_DRIFT', label: 'Inject Pressure Drift', description: 'Gradual pressure drift' },
  { value: 'HUMIDITY_DRIFT', label: 'Inject Humidity Drift', description: 'Gradual humidity drift' },
  { value: 'FROZEN_SENSOR', label: 'Freeze Sensor', description: 'Stuck sensor reading' },
  { value: 'MISSING_OBSERVATIONS', label: 'Missing Observations', description: 'Data gaps' },
  { value: 'DUPLICATE_OBSERVATIONS', label: 'Duplicate Observations', description: 'Repeated timestamps' },
  { value: 'COMMUNICATION_FAILURE', label: 'Communication Failure', description: 'Transmission issues' },
  { value: 'RANDOM_NOISE', label: 'Random Noise', description: 'Increased sensor noise' },
  { value: 'MULTIVARIATE_INCONSISTENCY', label: 'Multivariate Anomaly', description: 'T-H-P relationship violation' },
  { value: 'SENSOR_DEGRADATION', label: 'Sensor Degradation', description: 'Progressive sensor degradation' },
]

export const SENSOR_TYPES = [
  { value: 'TEMPERATURE', label: 'Temperature', unit: '°C', color: '#ef4444' },
  { value: 'PRESSURE', label: 'Pressure', unit: 'hPa', color: '#3b82f6' },
  { value: 'HUMIDITY', label: 'Humidity', unit: '%', color: '#22c55e' },
]

export const STATION_COORDS = [
  { station_id: 'AWS001', name: 'New Delhi', lat: 28.6139, lng: 77.2090 },
  { station_id: 'AWS002', name: 'Mumbai', lat: 19.0760, lng: 72.8777 },
  { station_id: 'AWS003', name: 'Bangalore', lat: 12.9716, lng: 77.5946 },
  { station_id: 'AWS004', name: 'Chennai', lat: 13.0827, lng: 80.2707 },
  { station_id: 'AWS005', name: 'Kolkata', lat: 22.5726, lng: 88.3639 },
  { station_id: 'AWS006', name: 'Hyderabad', lat: 17.3850, lng: 78.4867 },
  { station_id: 'AWS007', name: 'Pune', lat: 18.5204, lng: 73.8567 },
  { station_id: 'AWS008', name: 'Ahmedabad', lat: 23.0225, lng: 72.5714 },
]

export const DEMO_STEPS = [
  { id: 'baseline', name: 'Healthy Baseline', description: 'All stations normal' },
  { id: 'temp_spike', name: 'Temperature Spike', description: 'AWS001: 31.5°C → 55.2°C' },
  { id: 'temp_drift', name: 'Sensor Drift', description: 'AWS002: Gradual drift' },
  { id: 'frozen', name: 'Frozen Sensor', description: 'AWS003: Humidity stuck' },
  { id: 'comm_fail', name: 'Comm Failure', description: 'AWS004: Data gaps' },
  { id: 'multivariate', name: 'Multivariate Anomaly', description: 'AWS005: T-H violation' },
  { id: 'pressure_spike', name: 'Pressure Spike', description: 'AWS006: 1013 → 1048 hPa' },
  { id: 'humidity_drop', name: 'Humidity Drop', description: 'AWS007: 65% → 25%' },
  { id: 'degradation', name: 'Sensor Degradation', description: 'AWS008: Increased noise' },
  { id: 'reset', name: 'Reset Demo', description: 'Clear all anomalies' },
]