import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { usePoll, formatTs } from '../hooks';
import {
  alertsApi,
  anomaliesApi,
  explainApi,
  observationsApi,
  sensorHealthApi,
  stationsApi,
} from '../api/client';
import type { Observation } from '../types';
import { Card, DataTable, EmptyState, ErrorState, Loading, Stat, StatusBadge, btnGhost } from '../components/ui';

function haversineKm(a: number, b: number, c: number, d: number): number {
  const r = 6371;
  const p1 = (a * Math.PI) / 180;
  const p2 = (c * Math.PI) / 180;
  const dp = ((c - a) * Math.PI) / 180;
  const dl = ((d - b) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

function mean(xs: number[]): number | null {
  const v = xs.filter((x) => Number.isFinite(x));
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

export default function StationIntelligence() {
  const { stationId = '' } = useParams();
  const station = usePoll(() => stationsApi.get(stationId), 60000, [stationId]);
  const health = usePoll(() => sensorHealthApi.detail(stationId).catch(() => null), 30000, [stationId]);
  const obs = usePoll(() => observationsApi.list({ station_id: stationId, limit: 500 }), 15000, [stationId]);
  const allObs = usePoll(() => observationsApi.list({ limit: 500 }), 30000);
  const allStations = usePoll(() => stationsApi.list(), 60000);
  const anomalies = usePoll(() => anomaliesApi.list({ station_id: stationId, limit: 50 }), 15000, [stationId]);
  const alerts = usePoll(() => alertsApi.list({ station_id: stationId, limit: 10 }), 15000, [stationId]);

  const latestAnomalyId = useMemo(() => (anomalies.data ?? [])[0]?.id ?? null, [anomalies.data]);
  const [classification, setClassification] = useState<Record<string, unknown> | null>(null);
  const [explanation, setExplanation] = useState<{ main_reason: string; conclusion: string; recommended_action: string } | null>(null);
  useEffect(() => {
    if (latestAnomalyId === null) {
      setClassification(null);
      setExplanation(null);
      return;
    }
    let cancelled = false;
    explainApi
      .get(latestAnomalyId)
      .then((r) => {
        if (cancelled) return;
        setClassification((r.stored_classification ?? null) as Record<string, unknown> | null);
        setExplanation(r.stored);
      })
      .catch(() => {
        if (!cancelled) {
          setClassification(null);
          setExplanation(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [latestAnomalyId]);

  const sorted = useMemo(
    () => [...(obs.data ?? [])].sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp)),
    [obs.data],
  );
  const current: Observation | undefined = sorted[sorted.length - 1];
  const baselineWindow = sorted.slice(-25, -1); // trailing 24 before current
  const baseline = {
    temperature: mean(baselineWindow.map((o) => o.temperature)),
    pressure: mean(baselineWindow.map((o) => o.pressure)),
    humidity: mean(baselineWindow.map((o) => o.humidity)),
  };

  // 7-day reporting reliability from cadence
  const reliability = useMemo(() => {
    const weekAgo = Date.now() - 7 * 86400 * 1000;
    const recent = sorted.filter((o) => +new Date(o.timestamp) >= weekAgo);
    if (recent.length < 3) return null;
    const gaps: number[] = [];
    for (let i = 1; i < recent.length; i++) {
      const dt = (+new Date(recent[i].timestamp) - +new Date(recent[i - 1].timestamp)) / 60000;
      if (dt > 0) gaps.push(dt);
    }
    if (!gaps.length) return null;
    const med = [...gaps].sort((a, b) => a - b)[Math.floor(gaps.length / 2)] || 60;
    const spanMin = (+new Date(recent[recent.length - 1].timestamp) - +new Date(recent[0].timestamp)) / 60000;
    const expected = Math.max(1, spanMin / med + 1);
    return Math.max(0, Math.min(100, (recent.length / expected) * 100));
  }, [sorted]);

  // Neighbors: nearest 4 by haversine with latest reading each
  const neighbors = useMemo(() => {
    if (!station.data || !allStations.data || !allObs.data) return [];
    const latestByStation = new Map<string, Observation>();
    for (const o of [...allObs.data].sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp))) {
      latestByStation.set(o.station_id, o);
    }
    return allStations.data
      .filter((s) => s.station_id !== stationId)
      .map((s) => ({
        ...s,
        distance: haversineKm(station.data!.latitude, station.data!.longitude, s.latitude, s.longitude),
        latest: latestByStation.get(s.station_id),
      }))
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 4);
  }, [station.data, allStations.data, allObs.data, stationId]);

  const spatial = useMemo(() => {
    if (!current || neighbors.length < 2) return null;
    const temps = neighbors.map((n) => n.latest?.temperature).filter((t): t is number => t !== undefined);
    if (temps.length < 2) return null;
    const m = temps.reduce((a, b) => a + b, 0) / temps.length;
    const sd = Math.sqrt(temps.reduce((a, b) => a + (b - m) ** 2, 0) / temps.length);
    const z = (current.temperature - m) / Math.max(sd, 0.5);
    return { mean: m, sd, z };
  }, [current, neighbors]);

  if (station.error) return <div className="p-4"><ErrorState message={station.error} onRetry={station.refresh} /></div>;
  if (!station.data || !obs.data) {
    return (
      <div className="p-4">
        <Loading />
      </div>
    );
  }
  const s = station.data;

  const diff = (k: 'temperature' | 'pressure' | 'humidity') =>
    current && baseline[k] !== null ? current[k] - (baseline[k] as number) : null;
  const diffFmt = (v: number | null, unit: string) =>
    v === null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}${unit}`;

  const recent60 = sorted.slice(-60).map((o) => ({
    t: new Date(o.timestamp).toLocaleTimeString(),
    temp: o.temperature,
    press: o.pressure,
    hum: o.humidity,
  }));
  const fullSeries = sorted.map((o) => ({
    t: new Date(o.timestamp).toLocaleString(),
    temp: o.temperature,
    press: o.pressure,
    hum: o.humidity,
  }));

  return (
    <div className="page-enter space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">{s.station_id} · Station Intelligence</h1>
        <StatusBadge value={health.data?.status ?? s.status} />
        <Link to={`/stations/${s.station_id}`} className="ml-auto text-sm text-blue-500 hover:underline">← Station overview</Link>
      </div>

      {/* IDENTITY ROW */}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-6">
        <Stat label="Status" value={s.status} />
        <Stat label="Health" value={health.data ? `${health.data.overall.toFixed(0)}/100` : '—'} accent={health.data && health.data.overall < 40 ? '#ef4444' : '#22c55e'} />
        <Stat label="Reliability (7d)" value={reliability !== null ? `${reliability.toFixed(0)}%` : '—'} sub="reporting cadence" />
        <Stat label="Last update" value={current ? new Date(current.timestamp).toLocaleString() : '—'} />
        <Stat label="Latitude" value={s.latitude.toFixed(4)} />
        <Stat label="Longitude" value={s.longitude.toFixed(4)} />
      </div>

      {/* CURRENT vs EXPECTED vs DIFFERENCE */}
      <Card title="Current vs expected" subtitle="Expected = trailing 24-reading mean baseline (from backend observations)">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm tabular-nums">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800">
                <th className="px-2 py-2">Parameter</th>
                <th className="px-2 py-2">Current</th>
                <th className="px-2 py-2">Expected</th>
                <th className="px-2 py-2">Difference (obs − exp)</th>
              </tr>
            </thead>
            <tbody>
              {([
                ['Temperature', 'temperature', '°C'],
                ['Pressure', 'pressure', 'hPa'],
                ['Humidity', 'humidity', '%'],
              ] as const).map(([label, k, unit]) => {
                const d = diff(k);
                return (
                  <tr key={k} className="border-b border-slate-100 dark:border-slate-800/60">
                    <td className="px-2 py-2 font-medium">{label}</td>
                    <td className="px-2 py-2 font-bold">{current ? `${current[k].toFixed(1)}${unit}` : '—'}</td>
                    <td className="px-2 py-2">{baseline[k] !== null ? `${(baseline[k] as number).toFixed(1)}${unit}` : '—'}</td>
                    <td className="px-2 py-2 font-bold" style={{ color: d !== null && Math.abs(d) > (k === 'temperature' ? 3 : k === 'pressure' ? 5 : 10) ? '#f97316' : undefined }}>
                      {diffFmt(d, unit)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* LIVE + HISTORICAL CHARTS */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Live charts" subtitle="Most recent 60 readings">
          {recent60.length === 0 ? <EmptyState message="No readings yet." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={recent60}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="t" tick={false} />
                <YAxis yAxisId="t" orientation="left" tick={{ fontSize: 10 }} width={40} />
                <YAxis yAxisId="p" orientation="right" hide />
                <Tooltip />
                <Line yAxisId="t" type="monotone" dataKey="temp" name="Temp °C" stroke="#ef4444" dot={false} strokeWidth={2} />
                <Line yAxisId="t" type="monotone" dataKey="hum" name="Hum %" stroke="#3b82f6" dot={false} />
                <Line yAxisId="p" type="monotone" dataKey="press" name="Press" stroke="#22c55e" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Historical charts" subtitle={`Full window · ${sorted.length} readings`}>
          {fullSeries.length === 0 ? <EmptyState message="No readings yet." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={fullSeries}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="t" tick={false} />
                <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} width={40} />
                <Tooltip />
                <Area type="monotone" dataKey="temp" name="Temp °C" stroke="#ef4444" fill="#ef444433" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* NEIGHBORS + SPATIAL */}
      <Card
        title="Neighboring-station comparison"
        subtitle={spatial ? `Neighbor mean ${spatial.mean.toFixed(1)}°C · σ ${spatial.sd.toFixed(2)} · station z = ${spatial.z >= 0 ? '+' : ''}${spatial.z.toFixed(1)}` : 'Need ≥2 neighbors with readings'}
      >
        {neighbors.length === 0 ? <EmptyState message="No neighboring stations with recent readings." /> : (
          <DataTable
            columns={[
              { header: 'Station', render: (n) => <span className="font-semibold">{n.station_id}{n.isSelf ? ' ★' : ''}</span> },
              { header: 'Name', render: (n) => <span className="text-xs">{n.name}</span> },
              { header: 'Dist km', render: (n) => (n.isSelf ? '—' : n.distance.toFixed(0)) },
              {
                header: 'Temp °C',
                render: (n) => {
                  const t = n.latest?.temperature;
                  if (t === undefined) return <span>—</span>;
                  const out = spatial !== null && Math.abs((t - spatial.mean) / Math.max(spatial.sd, 0.5)) > 2;
                  return (
                    <span className={`font-bold ${out ? 'rounded bg-red-500/15 px-1.5 py-0.5 text-red-500' : ''}`}>
                      {t.toFixed(1)}{out ? ' ⚠ OUTLIER' : ''}
                    </span>
                  );
                },
              },
              { header: 'Press', render: (n) => (n.latest ? n.latest.pressure.toFixed(0) : '—') },
              { header: 'Hum', render: (n) => (n.latest ? n.latest.humidity.toFixed(0) : '—') },
            ]}
            rows={[
              { station_id: s.station_id, name: `${s.name} (this station)`, distance: 0, latest: current, isSelf: true },
              ...neighbors.map((n) => ({ ...n, isSelf: false })),
            ]}
            rowKey={(n) => n.station_id}
          />
        )}
        {spatial && Math.abs(spatial.z) > 2 && current && (
          <p className="mt-2 rounded-lg bg-red-500/10 p-2 text-sm font-semibold text-red-500">
            ⚠ {s.station_id} at {current.temperature.toFixed(1)}°C is an outlier vs neighbors (z = {spatial.z >= 0 ? '+' : ''}{spatial.z.toFixed(1)})
          </p>
        )}
        {spatial && Math.abs(spatial.z) <= 2 && (
          <p className="mt-2 text-sm text-emerald-500">✓ Consistent with neighboring stations.</p>
        )}
      </Card>

      {/* MULTIVARIATE + HEALTH TREND */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Multivariate consistency" subtitle="From the latest anomaly classification (backend)">
          {classification ? (
            <div className="grid grid-cols-3 gap-2 text-sm tabular-nums">
              {['spatial_consistency', 'temporal_consistency', 'multivariate_consistency'].map((k) => (
                <div key={k} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                  <p className="text-[11px] uppercase text-slate-500">{k.replace('_consistency', '')}</p>
                  <p className="text-lg font-bold">{Number(classification[k] as number ?? 0).toFixed(2)}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No classified anomaly yet — multivariate verdict appears after the first flag." />
          )}
        </Card>
        <Card title="Sensor health trend" subtitle="Trailing-window overall per day">
          {!health.data || health.data.trend.length === 0 ? <EmptyState message="No trend yet." /> : (
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={health.data.trend}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} width={32} />
                <Tooltip />
                <Line type="monotone" dataKey="score" stroke="#8b5cf6" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* ANOMALY HISTORY + ALERTS */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Anomaly history" subtitle={`${(anomalies.data ?? []).length} flagged`}>
          {(anomalies.data ?? []).length === 0 ? <EmptyState message="Clean record — no anomalies." /> : (
            <DataTable
              columns={[
                { header: 'Time', render: (a) => <span className="whitespace-nowrap">{formatTs(a.timestamp)}</span> },
                { header: 'Type', render: (a) => <span className="text-xs">{a.root_cause}</span> },
                { header: 'Score', render: (a) => <span className="font-bold">{a.score.toFixed(0)}</span> },
                { header: '', render: (a) => <button className={btnGhost} onClick={() => (window.location.hash = `#/anomalies/${a.id}`)}>Why?</button> },
              ]}
              rows={(anomalies.data ?? []).slice(0, 10)}
              rowKey={(a) => a.id}
            />
          )}
        </Card>
        <Card title="Recent alerts" subtitle="Raised for this station">
          {(alerts.data ?? []).length === 0 ? <EmptyState message="No alerts." /> : (
            <ul className="space-y-1.5 text-sm">
              {(alerts.data ?? []).slice(0, 8).map((a) => (
                <li key={a.id} className="flex gap-2">
                  <span className="font-semibold">{a.severity}</span>
                  <span className="flex-1">{a.message}</span>
                  <span className="text-xs text-slate-500">{formatTs(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* AI INSIGHTS */}
      <Card title="AI insights" subtitle="Latest verdict, generated from live detector outputs">
        {!explanation ? (
          <EmptyState message="No AI verdict yet — appears after the first flagged anomaly." />
        ) : (
          <div className="space-y-2 text-sm">
            <p className="rounded-lg bg-blue-500/10 p-3 font-medium leading-relaxed">{explanation.main_reason}</p>
            <p className="font-semibold">{explanation.conclusion}</p>
            <p><span className="font-semibold">Action: </span>{explanation.recommended_action}</p>
          </div>
        )}
      </Card>
    </div>
  );
}
