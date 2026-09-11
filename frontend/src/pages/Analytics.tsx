import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { usePoll } from '../hooks';
import { anomaliesApi, observationsApi, stationsApi } from '../api/client';
import { Card, EmptyState, ErrorState, Loading, inputCls } from '../components/ui';

export default function Analytics() {
  const [station, setStation] = useState('');
  const stations = usePoll(() => stationsApi.list(), 60000);
  const anomalies = usePoll(() => anomaliesApi.list({ limit: 500 }), 30000);
  const obs = usePoll(() => observationsApi.list({ station_id: station || undefined, limit: 500 }), 30000, [station]);

  if (anomalies.error) return <div className="p-4"><ErrorState message={anomalies.error} onRetry={anomalies.refresh} /></div>;
  if (!anomalies.data) return <div className="p-4"><Loading /></div>;

  const byType: Record<string, number> = {};
  const bySeverity: Record<string, number> = {};
  const byStation: Record<string, number> = {};
  for (const a of anomalies.data) {
    byType[a.root_cause] = (byType[a.root_cause] ?? 0) + 1;
    bySeverity[a.severity] = (bySeverity[a.severity] ?? 0) + 1;
    byStation[a.station_id] = (byStation[a.station_id] ?? 0) + 1;
  }
  const toBars = (m: Record<string, number>) => Object.entries(m).map(([name, count]) => ({ name, count }));

  const temps = (obs.data ?? []).map((o) => o.temperature);
  const stats =
    temps.length > 0
      ? {
          n: temps.length,
          min: Math.min(...temps).toFixed(1),
          max: Math.max(...temps).toFixed(1),
          mean: (temps.reduce((a, b) => a + b, 0) / temps.length).toFixed(1),
        }
      : null;

  return (
    <div className="page-enter space-y-4 p-4">
      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="By anomaly type" subtitle={`${anomalies.data.length} flagged`}>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={toBars(byType)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#f97316" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="By severity" subtitle="Detection bands">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={toBars(bySeverity)}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="By station" subtitle="Flagged count per AWS">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={toBars(byStation)}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card
        title="Temperature sample"
        subtitle={stats ? `${stats.n} readings · min ${stats.min} · mean ${stats.mean} · max ${stats.max} °C` : 'No readings'}
        action={
          <select value={station} onChange={(e) => setStation(e.target.value)} className={inputCls}>
            <option value="">All stations</option>
            {(stations.data ?? []).map((s) => (
              <option key={s.station_id} value={s.station_id}>{s.station_id}</option>
            ))}
          </select>
        }
      >
        {(obs.data ?? []).length === 0 ? (
          <EmptyState message="No observations in range." />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={(() => {
                const bins = new Array(12).fill(0);
                const lo = Math.min(...temps);
                const hi = Math.max(...temps);
                const span = hi - lo || 1;
                for (const t of temps) bins[Math.min(11, Math.floor(((t - lo) / span) * 12))]++;
                return bins.map((count, i) => ({ bin: `${(lo + (span * i) / 12).toFixed(0)}°`, count }));
              })()}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="count" name="Readings" fill="#22c55e" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  );
}
