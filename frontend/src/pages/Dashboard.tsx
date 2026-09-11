import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { usePoll, formatTs } from '../hooks';
import { alertsApi, anomaliesApi, explainApi, observationsApi, sensorHealthApi, stationsApi, wsUrl } from '../api/client';
import type { Anomaly, TickMessage } from '../types';
import { Card, EmptyState, ErrorState, Loading, Stat, StatusBadge, btnGhost, inputCls } from '../components/ui';
import StationMap, { type AnomalyMark } from '../components/StationMap';

type Zone = 'ALL' | 'NORTH' | 'CENTRAL' | 'SOUTH';

function zoneOf(lat: number): Exclude<Zone, 'ALL'> {
  if (lat >= 25) return 'NORTH';
  if (lat >= 20) return 'CENTRAL';
  return 'SOUTH';
}

function MiniSeries({ data, color, height = 120 }: { data: { t: string; v: number }[]; color: string; height?: number }) {
  if (data.length === 0) return <EmptyState message="Awaiting readings…" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
        <XAxis dataKey="t" tick={false} />
        <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} width={38} />
        <Tooltip />
        <Area type="monotone" dataKey="v" stroke={color} fill={`${color}33`} dot={false} strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const stations = usePoll(() => stationsApi.list(), 30000);
  const health = usePoll(() => sensorHealthApi.overview(), 15000);
  const anomalies = usePoll(() => anomaliesApi.list({ limit: 200 }), 10000);
  const alerts = usePoll(() => alertsApi.list({ limit: 20 }), 10000);
  const obs = usePoll(() => observationsApi.list({ limit: 400 }), 15000);

  const [zone, setZone] = useState<Zone>('ALL');
  const [mapSearch, setMapSearch] = useState('');
  const [cluster, setCluster] = useState(true);
  const [heat, setHeat] = useState(false);
  const [heatMetric, setHeatMetric] = useState<'health' | 'anomaly'>('health');
  const [liveTicks, setLiveTicks] = useState<TickMessage[]>([]);
  const [wsUp, setWsUp] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Real-time tick stream (read-only; Live Monitor owns controls)
  useEffect(() => {
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;
    ws.onopen = () => setWsUp(true);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'tick') setLiveTicks((t) => [msg as TickMessage, ...t].slice(0, 10));
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => setWsUp(false);
    return () => ws.close();
  }, []);

  const latestAnomalyId = useMemo(() => (anomalies.data ?? [])[0]?.id ?? null, [anomalies]);
  const [insight, setInsight] = useState<{ main: string; event: string | null } | null>(null);
  useEffect(() => {
    if (latestAnomalyId === null) {
      setInsight(null);
      return;
    }
    let cancelled = false;
    explainApi
      .get(latestAnomalyId)
      .then((r) => {
        if (!cancelled && r.stored) setInsight({ main: r.stored.main_reason, event: r.stored.event_type });
      })
      .catch(() => {
        if (!cancelled) setInsight(null);
      });
    return () => {
      cancelled = true;
    };
  }, [latestAnomalyId]);

  const healthByStation = useMemo(
    () => Object.fromEntries((health.data ?? []).map((h) => [h.station_id, h.status])),
    [health.data],
  );
  const healthScore = useMemo(
    () => Object.fromEntries((health.data ?? []).map((h) => [h.station_id, h.overall])),
    [health.data],
  );

  const anomalyByStation = useMemo(() => {
    const m: Record<string, AnomalyMark> = {};
    for (const a of anomalies.data ?? []) {
      const prev = m[a.station_id];
      if (!prev || +new Date(a.timestamp) > +(m[a.station_id] as unknown as { ts: string }).ts) {
        m[a.station_id] = { severity: a.severity, root_cause: a.root_cause, score: a.score };
        (m[a.station_id] as unknown as Record<string, string>).ts = a.timestamp;
      }
    }
    return m;
  }, [anomalies]);

  const visibleStations = useMemo(
    () => (stations.data ?? []).filter((s) => zone === 'ALL' || zoneOf(s.latitude) === zone),
    [stations, zone],
  );

  // ---- KPIs (all from APIs) ----
  const total = stations.data?.length ?? 0;
  const healthy = (health.data ?? []).filter((h) => h.status === 'EXCELLENT' || h.status === 'GOOD').length;
  const warning = (health.data ?? []).filter((h) => h.status === 'WARNING').length;
  const critical = (health.data ?? []).filter((h) => h.status === 'CRITICAL').length;
  const offline = (stations.data ?? []).filter((s) => s.status === 'OFFLINE').length;
  const dayAgo = Date.now() - 24 * 3600 * 1000;
  const activeAnomalies = (anomalies.data ?? []).filter((a) => +new Date(a.timestamp) >= dayAgo).length;
  const fleetHealth = (health.data ?? []).length
    ? (health.data ?? []).reduce((a, h) => a + h.overall, 0) / (health.data ?? []).length
    : 0;
  const dataQuality = useMemo(() => {
    const all = (health.data ?? []).flatMap((h) => h.sensors);
    if (all.length === 0) return 0;
    const penalty =
      all.reduce((a, s) => a + (s.penalties.missing_observations ?? 0) + (s.penalties.communication_failures ?? 0), 0) /
      all.length;
    return Math.max(0, 100 - penalty * 2);
  }, [health.data]);

  // ---- Bottom panels ----
  const byStation = useMemo(() => {
    const m = new Map<string, { t: string; temperature: number; pressure: number; humidity: number }[]>();
    for (const o of [...(obs.data ?? [])].sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp)).slice(-120)) {
      const arr = m.get(o.station_id) ?? [];
      arr.push({ t: new Date(o.timestamp).toLocaleTimeString(), temperature: o.temperature, pressure: o.pressure, humidity: o.humidity });
      m.set(o.station_id, arr);
    }
    return m;
  }, [obs.data]);
  const firstSeries = [...byStation.values()][0] ?? [];
  const focusStation = [...byStation.keys()][0];

  const timeline = useMemo(() => {
    const buckets = new Map<string, number>();
    for (const a of anomalies.data ?? []) {
      const d = new Date(a.timestamp);
      if (Number.isNaN(+d) || +d < dayAgo) continue;
      const key = `${String(d.getHours()).padStart(2, '0')}:00`;
      buckets.set(key, (buckets.get(key) ?? 0) + 1);
    }
    return [...buckets.entries()].sort().map(([t, count]) => ({ t, count }));
  }, [anomalies.data]);

  const worstSensors = useMemo(
    () =>
      (health.data ?? [])
        .flatMap((h) => h.sensors.map((s) => ({ station: h.station_id, sensor_type: s.sensor_type, score: s.score })))
        .sort((a, b) => a.score - b.score)
        .slice(0, 6),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [health.data],
  );

  const feed = useMemo(() => {
    const items: { key: string; time: string; text: string; severity: string; live?: boolean; anomalyId?: number }[] =
      (alerts.data ?? []).map((a) => ({
        key: `a-${a.id}`,
        time: a.created_at,
        text: a.message,
        severity: a.severity,
        anomalyId: a.anomaly_id ?? undefined,
      }));
    for (const t of liveTicks) {
      for (const d of t.detections) {
        items.unshift({
          key: `live-${t.tick}-${d.station_id}`,
          time: new Date().toISOString(),
          text: `${d.station_id}: ${d.anomaly_type} (${d.anomaly_score?.toFixed(0)}) · ${d.event_type}`,
          severity: (d.anomaly_score ?? 0) >= 70 ? 'HIGH' : 'SUSPICIOUS',
          live: true,
        });
      }
    }
    return items.slice(0, 25);
  }, [alerts.data, liveTicks]);

  if (stations.error || health.error) {
    return (
      <div className="page-enter p-4">
        <ErrorState message={stations.error ?? health.error ?? ''} onRetry={() => { stations.refresh(); health.refresh(); }} />
      </div>
    );
  }
  if (!stations.data || !health.data) {
    return (
      <div className="p-4">
        <Loading />
      </div>
    );
  }

  const legend = [
    { c: '#22c55e', label: `Healthy ${healthy}` },
    { c: '#facc15', label: `Warning ${warning}` },
    { c: '#ef4444', label: `Critical ${critical}` },
    { c: '#64748b', label: `Offline ${offline}` },
  ];

  return (
    <div className="page-enter space-y-4 p-4">
      {/* KPI ROW */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
        <Stat label="Total Stations" value={total} sub="IMD AWS network" />
        <Stat label="Healthy" value={healthy} sub="Excellent + Good" accent="#22c55e" />
        <Stat label="Warning" value={warning} sub="degraded sensors" accent={warning ? '#facc15' : undefined} />
        <Stat label="Critical" value={critical} sub="act now" accent={critical ? '#ef4444' : '#22c55e'} />
        <Stat label="Offline" value={offline} sub="no telemetry" accent={offline ? '#64748b' : undefined} />
        <Stat label="Active Anomalies" value={activeAnomalies} sub="last 24h" accent={activeAnomalies ? '#f97316' : undefined} />
        <Stat label="Data Quality" value={`${dataQuality.toFixed(0)}%`} sub="gaps + comm penalties" accent={dataQuality >= 90 ? '#22c55e' : '#facc15'} />
        <Stat label="Fleet Health" value={`${fleetHealth.toFixed(0)}/100`} sub="mean overall" accent={fleetHealth >= 65 ? '#22c55e' : '#f97316'} />
      </div>

      {/* MAP + FEED */}
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold tracking-wide">INTERACTIVE INDIA AWS MAP</h2>
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-bold ${wsUp ? 'bg-emerald-500/15 text-emerald-500' : 'bg-slate-500/15 text-slate-500'}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${wsUp ? 'animate-pulse bg-emerald-500' : 'bg-slate-500'}`} />
                {wsUp ? 'STREAMING' : 'POLLING'}
              </span>
              <div className="ml-auto flex flex-wrap items-center gap-2">
                <input
                  value={mapSearch}
                  onChange={(e) => setMapSearch(e.target.value)}
                  placeholder="Search + zoom…"
                  className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-800"
                />
                <select value={zone} onChange={(e) => setZone(e.target.value as Zone)} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-800">
                  <option value="ALL">All regions</option>
                  <option value="NORTH">North (≥25°N)</option>
                  <option value="CENTRAL">Central (20–25°N)</option>
                  <option value="SOUTH">South (&lt;20°N)</option>
                </select>
                <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={cluster} onChange={(e) => setCluster(e.target.checked)} /> Cluster</label>
                <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={heat} onChange={(e) => setHeat(e.target.checked)} /> Heatmap</label>
                {heat && (
                  <select value={heatMetric} onChange={(e) => setHeatMetric(e.target.value as 'health' | 'anomaly')} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-800">
                    <option value="health">Heat: health gap</option>
                    <option value="anomaly">Heat: anomalies</option>
                  </select>
                )}
              </div>
            </div>
            <StationMap
              stations={visibleStations}
              healthByStation={healthByStation}
              healthScore={healthScore}
              anomalyByStation={anomalyByStation}
              height={470}
              cluster={cluster}
              showHeatmap={heat}
              heatMetric={heatMetric}
              searchQuery={mapSearch}
            />
            <div className="mt-2 flex flex-wrap gap-3 text-xs">
              {legend.map((l) => (
                <span key={l.label} className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: l.c }} />
                  {l.label}
                </span>
              ))}
              <span className="inline-flex items-center gap-1.5 text-slate-500">◉ pulsing ring = active anomaly</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-1 text-sm font-semibold tracking-wide">LIVE ALERT FEED</h2>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">Backend alerts + streaming detections (LIVE)</p>
          <ul className="max-h-[480px] space-y-2 overflow-y-auto pr-1">
            {feed.length === 0 && <li className="text-sm text-slate-500">No alerts — network nominal.</li>}
            {feed.map((f) => (
              <li key={f.key} className="flex items-start gap-2 rounded-lg border border-slate-200 px-2.5 py-2 text-xs dark:border-slate-800">
                <StatusBadge value={f.severity} pulse={f.live} />
                <div className="min-w-0 flex-1">
                  <p className="break-words">{f.text}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    {f.live ? 'LIVE tick' : formatTs(f.time)}
                    {f.anomalyId !== undefined && (
                      <button onClick={() => navigate(`/anomalies/${f.anomalyId}`)} className="ml-2 font-semibold text-blue-500 hover:underline">
                        Explain →
                      </button>
                    )}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* BOTTOM PANELS */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h3 className="mb-2 text-sm font-semibold">Live Temperature {focusStation && <span className="text-xs font-normal text-slate-500">· {focusStation} + network</span>}</h3>
          <MiniSeries data={firstSeries.map((p) => ({ t: p.t, v: p.temperature }))} color="#ef4444" />
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h3 className="mb-2 text-sm font-semibold">Live Pressure</h3>
          <MiniSeries data={firstSeries.map((p) => ({ t: p.t, v: p.pressure }))} color="#22c55e" />
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h3 className="mb-2 text-sm font-semibold">Live Humidity</h3>
          <MiniSeries data={firstSeries.map((p) => ({ t: p.t, v: p.humidity }))} color="#3b82f6" />
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h3 className="mb-2 text-sm font-semibold">Anomaly Timeline <span className="text-xs font-normal text-slate-500">· per-hour, 24h</span></h3>
          {timeline.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">No anomalies in the last 24h.</p>
          ) : (
            <ResponsiveContainer width="100%" height={120}>
              <BarChart data={timeline}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                <XAxis dataKey="t" tick={{ fontSize: 10 }} interval={2} />
                <YAxis tick={{ fontSize: 10 }} width={28} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#f97316" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h3 className="mb-2 text-sm font-semibold">Sensor Health <span className="text-xs font-normal text-slate-500">· weakest first</span></h3>
          {worstSensors.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">No health data.</p>
          ) : (
            <ul className="space-y-1.5 text-xs tabular-nums">
              {worstSensors.map((s) => (
                <li key={`${s.station}-${s.sensor_type}`} className="flex items-center gap-2">
                  <span className="w-24 truncate font-semibold">{s.station}</span>
                  <span className="w-24 truncate text-slate-500">{s.sensor_type}</span>
                  <span className="flex-1">
                    <span className="block h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                      <span
                        className="block h-full rounded-full"
                        style={{ width: `${s.score}%`, backgroundColor: s.score >= 65 ? '#22c55e' : s.score >= 40 ? '#facc15' : '#ef4444' }}
                      />
                    </span>
                  </span>
                  <span className="w-12 text-right font-bold">{s.score.toFixed(0)}</span>
                </li>
              ))}
            </ul>
          )}
          <Link to="/health" className="mt-2 inline-block text-xs font-semibold text-blue-500 hover:underline">Full health →</Link>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h3 className="mb-2 text-sm font-semibold">AI Insights <span className="text-xs font-normal text-slate-500">· latest verdict</span></h3>
          {!anomalies.data?.length ? (
            <p className="py-8 text-center text-sm text-slate-500">No anomalies to explain yet.</p>
          ) : insight ? (
            <div className="space-y-2 text-sm">
              <p><StatusBadge value={(anomalies.data as Anomaly[])[0].severity} /> <span className="font-semibold">{(anomalies.data as Anomaly[])[0].root_cause}</span></p>
              <p className="leading-relaxed">{insight.main}</p>
              <p className="text-xs text-slate-500">Event: {insight.event ?? '—'}</p>
              <button onClick={() => navigate(`/anomalies/${(anomalies.data as Anomaly[])[0].id}`)} className="text-xs font-semibold text-blue-500 hover:underline">
                Full explanation →
              </button>
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-slate-500">Loading verdict…</p>
          )}
        </div>
      </div>

      {/* CHART: network temperature traces */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <h3 className="mb-2 text-sm font-semibold">Network temperature traces <span className="text-xs font-normal text-slate-500">· per station, latest 120 readings</span></h3>
        <NetworkTempChart byStation={byStation} />
      </div>
    </div>
  );
}

function NetworkTempChart({ byStation }: { byStation: Map<string, { t: string; temperature: number }[]> }) {
  const entries = [...byStation.entries()].slice(0, 8);
  if (entries.length === 0) return <p className="py-8 text-center text-sm text-slate-500">Awaiting readings…</p>;
  const merged = new Map<string, Record<string, number | string>>();
  for (const [sid, pts] of entries) {
    for (const p of pts) {
      const row = merged.get(p.t) ?? { t: p.t };
      row[sid] = p.temperature;
      merged.set(p.t, row);
    }
  }
  const data = [...merged.values()];
  const colors = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'];
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
        <XAxis dataKey="t" tick={false} />
        <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} width={40} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {entries.map(([sid], i) => (
          <Line key={sid} type="monotone" dataKey={sid} stroke={colors[i % colors.length]} dot={false} strokeWidth={1.5} connectNulls />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
