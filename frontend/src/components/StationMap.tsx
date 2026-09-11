import { useEffect } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import 'leaflet.markercluster';
import 'leaflet.heat';
import type { Station } from '../types';

export interface AnomalyMark {
  severity: string;
  root_cause: string;
  score: number;
}

const HEALTH_COLORS: Record<string, string> = {
  EXCELLENT: '#22c55e',
  GOOD: '#84cc16',
  WARNING: '#facc15',
  CRITICAL: '#ef4444',
  OFFLINE: '#64748b',
};

const SEV_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, SUSPICIOUS: 2, LOW: 1, NORMAL: 0 };

function worstColor(statuses: string[]): string {
  const order = ['CRITICAL', 'WARNING', 'OFFLINE', 'GOOD', 'EXCELLENT'];
  for (const s of order) if (statuses.includes(s)) return HEALTH_COLORS[s];
  return '#3b82f6';
}

function Layers({
  stations,
  healthByStation,
  healthScore,
  anomalyByStation,
  cluster,
  showHeatmap,
  heatMetric,
  searchQuery,
}: {
  stations: Station[];
  healthByStation: Record<string, string>;
  healthScore: Record<string, number>;
  anomalyByStation: Record<string, AnomalyMark>;
  cluster: boolean;
  showHeatmap: boolean;
  heatMetric: 'health' | 'anomaly';
  searchQuery: string;
}) {
  const map = useMap();

  useEffect(() => {
    const clusterGroup = (L as unknown as { markerClusterGroup: (o: object) => L.LayerGroup }).markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 45,
      iconCreateFunction: (c: { getAllChildMarkers: () => L.Marker[]; getChildCount: () => number }) => {
        const markers = c.getAllChildMarkers();
        const statuses = markers.map((m) => (m.options as Record<string, unknown>).healthStatus as string).filter(Boolean);
        const color = worstColor(statuses);
        return L.divIcon({
          html: `<div class="cc-cluster" style="background:${color}33;border:2px solid ${color};color:${color}">${c.getChildCount()}</div>`,
          className: 'cc-cluster-wrap',
          iconSize: L.point(40, 40),
        });
      },
    });
    const plainGroup = L.layerGroup();
    const target = cluster ? clusterGroup : plainGroup;

    stations.forEach((s) => {
      const h = healthByStation[s.station_id];
      const color = (h && HEALTH_COLORS[h]) || '#3b82f6';
      const anomaly = anomalyByStation[s.station_id];
      const score = healthScore[s.station_id];
      const popupHtml =
        `<div style="min-width:190px;font-family:Inter,system-ui,sans-serif">` +
        `<b>${s.station_id}</b> · ${s.name}<br/>` +
        `<span>Health: <b>${h ?? s.status}</b>${score !== undefined ? ` (${score.toFixed(0)}/100)` : ''}</span><br/>` +
        (anomaly
          ? `<span style="color:#f97316">▲ ${anomaly.root_cause} · score ${anomaly.score.toFixed(0)} (${anomaly.severity})</span><br/>`
          : `<span style="color:#22c55e">● Nominal</span><br/>`) +
        `<a href="#/stations/${s.station_id}" style="color:#3b82f6;font-weight:600">Open station →</a>` +
        `</div>`;
      const marker = L.circleMarker([s.latitude, s.longitude], {
        radius: anomaly ? 12 : 9,
        color,
        fillColor: color,
        fillOpacity: anomaly ? 0.85 : 0.6,
        weight: 2,
      } as L.CircleMarkerOptions & { healthStatus: string });
      (marker.options as Record<string, unknown>).healthStatus = h ?? 'UNKNOWN';
      marker.bindPopup(popupHtml);
      marker.bindTooltip(`<b>${s.station_id}</b> · ${s.name}${h ? `<br/>Health: ${h}` : ''}`, { direction: 'top' });
      target.addLayer(marker);

      if (anomaly) {
        const pulse = L.marker([s.latitude, s.longitude], {
          icon: L.divIcon({ html: '<div class="cc-pulse"></div>', className: 'cc-pulse-wrap', iconSize: [24, 24], iconAnchor: [12, 12] }),
          interactive: false,
          keyboard: false,
        });
        plainGroup.addLayer(pulse);
      }
    });
    map.addLayer(target);
    map.addLayer(plainGroup);

    let heat: L.Layer | null = null;
    if (showHeatmap && stations.length > 0) {
      const pts: Array<[number, number, number]> = stations.map((s) => {
        const intensity =
          heatMetric === 'anomaly'
            ? anomalyByStation[s.station_id]
              ? Math.min(1, (SEV_RANK[anomalyByStation[s.station_id].severity] ?? 1) / 4 + 0.25)
              : 0.02
            : 1 - (healthScore[s.station_id] ?? 100) / 100;
        return [s.latitude, s.longitude, Math.max(0.02, Math.min(1, intensity))];
      });
      heat = (L as unknown as { heatLayer: (p: Array<[number, number, number]>, o: object) => L.Layer }).heatLayer(pts, {
        radius: 28,
        blur: 22,
        maxZoom: 10,
        gradient: { 0.2: '#3b82f6', 0.45: '#22c55e', 0.65: '#facc15', 0.85: '#f97316', 1: '#ef4444' },
      });
      map.addLayer(heat);
    }
    return () => {
      map.removeLayer(target);
      map.removeLayer(plainGroup);
      if (heat) map.removeLayer(heat);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, stations, healthByStation, healthScore, anomalyByStation, cluster, showHeatmap, heatMetric]);

  // Search-to-zoom
  useEffect(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return;
    const hit = stations.find(
      (s) => s.station_id.toLowerCase().includes(q) || s.name.toLowerCase().includes(q),
    );
    if (hit) map.flyTo([hit.latitude, hit.longitude], 8, { duration: 0.8 });
  }, [map, searchQuery, stations]);

  return null;
}

export default function StationMap({
  stations,
  healthByStation = {},
  healthScore = {},
  anomalyByStation = {},
  height = 460,
  cluster = true,
  showHeatmap = false,
  heatMetric = 'health',
  searchQuery = '',
}: {
  stations: Station[];
  healthByStation?: Record<string, string>;
  healthScore?: Record<string, number>;
  anomalyByStation?: Record<string, AnomalyMark>;
  height?: number;
  cluster?: boolean;
  showHeatmap?: boolean;
  heatMetric?: 'health' | 'anomaly';
  searchQuery?: string;
}) {
  if (stations.length === 0) return <p className="py-6 text-center text-sm text-slate-500">No stations to map.</p>;
  const center: [number, number] = [
    stations.reduce((a, s) => a + s.latitude, 0) / stations.length,
    stations.reduce((a, s) => a + s.longitude, 0) / stations.length,
  ];
  return (
    <MapContainer center={center} zoom={5} style={{ height, width: '100%', borderRadius: 12 }} scrollWheelZoom zoomControl>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Layers
        stations={stations}
        healthByStation={healthByStation}
        healthScore={healthScore}
        anomalyByStation={anomalyByStation}
        cluster={cluster}
        showHeatmap={showHeatmap}
        heatMetric={heatMetric}
        searchQuery={searchQuery}
      />
    </MapContainer>
  );
}
