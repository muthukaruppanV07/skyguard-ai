// Backend DTOs (mirror backend/app/schemas/schemas.py + route shapes)

export interface Station {
  station_id: string;
  name: string;
  latitude: number;
  longitude: number;
  status: string;
}

export interface Observation {
  id: number;
  station_id: string;
  timestamp: string;
  temperature: number;
  pressure: number;
  humidity: number;
}

export interface Anomaly {
  id: number;
  station_id: string;
  observation_id: number | null;
  timestamp: string;
  score: number;
  severity: string;
  root_cause: string;
  message: string;
  confidence: number;
  resolved: boolean;
}

export interface Alert {
  id: number;
  station_id: string;
  anomaly_id: number | null;
  severity: string;
  message: string;
  acknowledged: boolean;
  muted: boolean;
  created_at: string;
}

export interface SensorScore {
  sensor_type: string;
  score: number;
  status: string;
  anomaly_count: number;
  penalties: Record<string, number>;
}

export interface StationHealthSummary {
  station_id: string;
  overall: number;
  status: string;
  worst_sensor: string;
  sensors: SensorScore[];
}

export interface StationHealthDetail extends StationHealthSummary {
  trend: { date: string; score: number; status: string }[];
}

export interface MaintenanceIntel {
  station_id: string;
  sensor_type: string;
  health: number;
  health_status: string;
  maintenance_risk: number;
  risk_level: string;
  maintenance_priority: string;
  reason: string;
  recommended_action: string[];
  signals: Record<string, unknown>;
}

export interface StationMaintenance {
  station_id: string;
  worst_risk: number;
  worst_sensor: string;
  sensors: MaintenanceIntel[];
  open_orders: {
    id: number;
    priority: string;
    recommendation: string;
    reason: string;
    status: string;
  }[];
}

export interface SimStatus {
  status: string;
  tick: number;
  scenario: string | null;
  stations: string[];
}

export interface Scenario {
  id: string;
  description: string;
}

export interface TickReading {
  station_id: string;
  timestamp?: string;
  temperature?: number;
  pressure?: number;
  humidity?: number;
  skipped?: boolean;
  skip_streak?: number;
  anomaly_type?: string;
  anomaly_score?: number;
  event_type?: string;
  alert_id?: number;
}

export interface TickMessage {
  type: string;
  tick: number;
  status: string;
  scenario: string | null;
  readings: TickReading[];
  detections: TickReading[];
}

export interface Explanation {
  station_id: string;
  anomaly_type: string;
  anomaly_score: number;
  severity: string;
  confidence: number;
  root_cause: string;
  event_type: string | null;
  main_reason: string;
  conclusion: string;
  supporting_evidence: string[];
  contributing_features: {
    feature: string;
    sensor: string;
    value: number | null;
    baseline: number | null;
    z_score: number | null;
    contribution: number;
    method: string;
  }[];
  methods_triggered: {
    detector: string;
    score: number;
    weight: number;
    contribution: number;
    triggered: boolean;
    method: string;
  }[];
  recommended_action: string;
  attribution_method: string;
  shap_available: boolean;
}

export interface ExplanationResponse {
  anomaly_id: number;
  stored: {
    main_reason: string;
    conclusion: string;
    root_cause: string;
    event_type: string | null;
    recommended_action: string;
    top_contributors: Explanation['contributing_features'];
    methods_triggered: string[];
  } | null;
  stored_classification: Record<string, unknown> | null;
  stored_guard: Record<string, unknown> | null;
  live: Explanation | null;
}

export interface Insight {
  id: string;
  kind: string;
  title: string;
  evidence: string[];
  affected_stations: string[];
  confidence: number;
  recommended_action: string;
  severity: string;
}

export interface QualityStation {
  station_id: string;
  completeness: number;
  validity: number;
  consistency: number;
  timeliness: number;
  overall: number;
  counts: Record<string, number>;
}

export interface QualityOverview {
  fleet: Record<string, number>;
  stations: QualityStation[];
  issue_counts: Record<string, number>;
  total_issues: number;
}

export interface QualityIssue {
  station_id: string;
  parameter: string;
  timestamp: string;
  issue_type: string;
  detail: string;
  severity: string;
}

export interface EvalMethodMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  fpr: number;
  confusion: { tp: number; fp: number; tn: number; fn: number };
  n: number;
}

export interface EvalRun {
  config: Record<string, number>;
  methods: { threshold: EvalMethodMetrics; hybrid: EvalMethodMetrics };
  latency: {
    threshold: { mean_steps: number | null; detected_episodes: number; total_episodes: number };
    hybrid: { mean_steps: number | null; detected_episodes: number; total_episodes: number };
  };
  categories: Record<string, { threshold: EvalMethodMetrics; hybrid: EvalMethodMetrics; n: number }>;
  episodes: number;
  ran_at?: string;
}

export interface SystemInfo {
  app: { name: string; version: string; environment: string };
  models: { name: string; artifact: string; present: boolean; size_bytes?: number; modified?: string; status: string }[];
  ml: { framework: string; sklearn: { installed: boolean; version: string | null }; inference_mode: string };
  training_status: string;
  detection_methods: { name: string; enabled: boolean; weight: number | null }[];
  features: { count: number; names: string[] };
  dataset: { stations: number; observations: number; anomalies: number; alerts: number };
  latency: { station_id: string | null; detection_latency_ms: number | null; inference_latency_ms: number | null; isolation_forest_ran: boolean; runs: number; reason?: string; measured_at?: string };
  ingestion: { observations_last_hour: number; per_minute: number; latest_observation: string | null };
  status: {
    api: { status: string; version: string };
    ml_engine: { status: string; isolation_forest_ran_in_probe: boolean };
    database: { status: string; file: { path: string; size_bytes: number } | null };
    streaming: { status: string; tick?: number; scenario?: string | null; subscribers?: number; tick_interval_s?: number | null; reason?: string };
  };
  pipeline: string[];
  generated_at: string;
}

export interface ReportSection {
  kind: string;
  label?: string;
  value?: string | number;
  columns?: string[];
  rows?: (string | number | null)[][];
  trends?: Record<string, { date: string; score: number; status: string }[]>;
}

export interface Report {
  title: string;
  report_type?: string;
  params?: { station_id: string | null; days: number };
  window_days?: number;
  summary: string;
  sections: ReportSection[];
  csv?: { columns: string[]; rows: Record<string, unknown>[] };
}

export interface ReportRun {
  id: number;
  report_type: string;
  params: { station_id: string | null; days: number };
  created_at: string;
  summary?: string;
  report?: Report;
}

export type Severity = 'NORMAL' | 'LOW' | 'SUSPICIOUS' | 'HIGH' | 'CRITICAL';

export interface SpatialNeighbor {
  station_id: string;
  name: string;
  distance_km: number;
  temperature: number | null;
  pressure: number | null;
  humidity: number | null;
  temp_deviation: number | null;
}

export interface SpatialIntel {
  station_id: string;
  timestamp: string | null;
  neighbors: SpatialNeighbor[];
  neighbor_agreement: string;
  spatial_deviation_c: number | null;
  spatial_z: number | null;
  neighbor_mean_c: number | null;
  regional_consistency: number | null;
  regional_band: string;
  classification_hint: string;
  method: Record<string, unknown>;
}

export interface SpatialOverviewStation {
  station_id: string;
  name: string;
  latitude: number;
  longitude: number;
  status: string;
  temperature: number | null;
  timestamp: string | null;
}
