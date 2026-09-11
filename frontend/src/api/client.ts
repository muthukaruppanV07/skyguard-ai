import axios from 'axios';
import type {
  Alert,
  Anomaly,
  EvalRun,
  Explanation,
  ExplanationResponse,
  Insight,
  Observation,
  QualityIssue,
  QualityOverview,
  Report,
  ReportRun,
  SystemInfo,
  Scenario,
  SimStatus,
  SpatialIntel,
  SpatialOverviewStation,
  Station,
  StationHealthDetail,
  StationHealthSummary,
  StationMaintenance,
} from '../types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api/v1',
  timeout: 30000,
});

export function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/ws/live`;
}

export const healthApi = {
  service: () => axios.get<{ status: string; service: string; version: string }>('/health').then((r) => r.data),
};

export const stationsApi = {
  list: () => api.get<Station[]>('/stations').then((r) => r.data),
  get: (id: string) => api.get<Station>(`/stations/${id}`).then((r) => r.data),
};

export const observationsApi = {
  list: (params?: { station_id?: string; limit?: number }) =>
    api.get<Observation[]>('/observations', { params }).then((r) => r.data),
  create: (payload: Omit<Observation, 'id'>) =>
    api.post<Observation>('/observations', payload).then((r) => r.data),
};

export const anomaliesApi = {
  list: (params?: { station_id?: string; limit?: number }) =>
    api.get<Anomaly[]>('/anomalies', { params }).then((r) => r.data),
  resolve: (id: number) => api.patch<Anomaly>(`/anomalies/${id}/resolve`).then((r) => r.data),
};

export const alertsApi = {
  list: (params?: { station_id?: string; limit?: number }) =>
    api.get<Alert[]>('/alerts', { params }).then((r) => r.data),
  acknowledge: (id: number, acknowledged = true) =>
    api.patch<Alert>(`/alerts/${id}`, { acknowledged }).then((r) => r.data),
  mute: (id: number, muted = true) =>
    api.patch<Alert>(`/alerts/${id}`, { muted }).then((r) => r.data),
};

export const sensorHealthApi = {
  overview: () => api.get<StationHealthSummary[]>('/sensor-health').then((r) => r.data),
  detail: (id: string) => api.get<StationHealthDetail>(`/sensor-health/${id}`).then((r) => r.data),
};

export const maintenanceApi = {
  list: () => api.get<StationMaintenance[]>('/maintenance').then((r) => r.data),
  get: (id: string) => api.get<StationMaintenance>(`/maintenance/${id}`).then((r) => r.data),
  sync: (id: string) => api.post<StationMaintenance>(`/maintenance/${id}/sync`).then((r) => r.data),
};

export const explainApi = {
  get: (id: number) => api.get<ExplanationResponse>(`/explanations/${id}`).then((r) => r.data),
  preview: (payload: {
    station_id: string;
    timestamp: string;
    temperature?: number | null;
    pressure?: number | null;
    humidity?: number | null;
  }) => api.post<Explanation>('/explanations/preview', payload).then((r) => r.data),
  detectAndExplain: (payload: {
    station_id: string;
    timestamp: string;
    temperature?: number | null;
    pressure?: number | null;
    humidity?: number | null;
  }) => api.post('/explanations/detect-and-explain', payload).then((r) => r.data),
};

export const datasetApi = {
  generate: (payload: {
    num_stations: number;
    num_observations: number;
    sampling_interval_minutes: number;
    anomaly_percentage: number;
    seed: number;
    ingest: boolean;
  }) => api.post('/dataset/generate', payload).then((r) => r.data),
  upload: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api.post('/dataset/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  templateUrl: () => `${api.defaults.baseURL}/dataset/template`,
};

export const qualityApi = {
  overview: (hours = 168) => api.get<QualityOverview>('/data-quality/overview', { params: { hours } }).then((r) => r.data),
  issues: (params?: { station_id?: string; parameter?: string; hours?: number; issue_type?: string; limit?: number }) =>
    api.get<{ total: number; issues: QualityIssue[]; known_issue_types: string[] }>('/data-quality/issues', { params }).then((r) => r.data),
};

export const reportsApi = {
  types: () => api.get<{ id: string; title: string }[]>('/reports/types').then((r) => r.data),
  preview: (payload: { report_type: string; station_id?: string | null; days?: number }) =>
    api.post<Report>('/reports/preview', payload, { timeout: 180000 }).then((r) => r.data),
  generate: (payload: { report_type: string; station_id?: string | null; days?: number }) =>
    api.post<{ id: number; report_type: string; created_at: string; report: Report }>('/reports/generate', payload, { timeout: 180000 }).then((r) => r.data),
  runs: (limit = 20) => api.get<ReportRun[]>('/reports', { params: { limit } }).then((r) => r.data),
  get: (id: number) => api.get<ReportRun & { report: Report }>('/reports/' + id).then((r) => r.data),
  exportUrl: (id: number, format: 'json' | 'csv') => `${api.defaults.baseURL}/reports/${id}/export?format=${format}`,
};

export const systemApi = {
  info: () => api.get<SystemInfo>('/system/info', { timeout: 120000 }).then((r) => r.data),
};

export const evalApi = {
  methods: () => api.get('/evaluation/methods').then((r) => r.data),
  run: (payload: { episodes_per_category?: number; history_points?: number; test_points?: number; step_minutes?: number; seed?: number }) =>
    api.post<EvalRun>('/evaluation/run', payload, { timeout: 600000 }).then((r) => r.data),
  latest: () => api.get<EvalRun>('/evaluation/latest').then((r) => r.data),
};

export const insightsApi = {
  list: (hours = 24) => api.get<Insight[]>('/insights', { params: { hours } }).then((r) => r.data),
};

export const spatialApi = {
  overview: () => api.get<SpatialOverviewStation[]>('/spatial/overview').then((r) => r.data),
  station: (id: string, params?: { radius_km?: number; k?: number }) =>
    api.get<SpatialIntel>(`/spatial/${id}`, { params }).then((r) => r.data),
};

export const simApi = {
  scenarios: () => api.get<Scenario[]>('/simulation/scenarios').then((r) => r.data),
  status: () => api.get<SimStatus>('/simulation/status').then((r) => r.data),
  start: () => api.post('/simulation/start').then((r) => r.data),
  pause: () => api.post('/simulation/pause').then((r) => r.data),
  resume: () => api.post('/simulation/resume').then((r) => r.data),
  stop: () => api.post('/simulation/stop').then((r) => r.data),
  reset: () => api.post('/simulation/reset').then((r) => r.data),
  inject: (payload: { scenario_id: string; station_ids?: string[]; duration_ticks?: number; magnitude?: number }) =>
    api.post('/simulation/inject', payload).then((r) => r.data),
  tick: () => api.post('/simulation/tick').then((r) => r.data),
};

export default api;
