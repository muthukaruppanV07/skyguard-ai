import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { usePoll, formatTs } from '../hooks';
import { anomaliesApi, observationsApi, sensorHealthApi, stationsApi } from '../api/client';
import { Card, DataTable, EmptyState, ErrorState, Loading, Stat, StatusBadge, btnGhost, inputCls } from '../components/ui';

export default function StationDetail() {
  const { stationId = '' } = useParams();
  const navigate = useNavigate();
  const [limit, setLimit] = useState(100);
  const station = usePoll(() => stationsApi.get(stationId), 60000, [stationId]);
  const health = usePoll(() => sensorHealthApi.detail(stationId).catch(() => null), 30000, [stationId]);
  const obs = usePoll(() => observationsApi.list({ station_id: stationId, limit }), 15000, [stationId, limit]);
  const anomalies = usePoll(() => anomaliesApi.list({ station_id: stationId, limit: 20 }), 15000, [stationId]);

  if (station.error) return <div className="p-4"><ErrorState message={station.error} onRetry={station.refresh} /></div>;
  if (!station.data) return <div className="p-4"><Loading /></div>;
  const s = station.data;

  const series = [...(obs.data ?? [])]
    .sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp))
    .map((o) => ({
      t: new Date(o.timestamp).toLocaleString(),
      temp: o.temperature,
      press: o.pressure,
      hum: o.humidity,
    }));

  return (
    <div className="page-enter space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">{s.station_id} · {s.name}</h1>
        <StatusBadge value={health.data?.status ?? s.status} />
        <span className="text-sm text-slate-500">({s.latitude.toFixed(2)}, {s.longitude.toFixed(2)})</span>
        <Link to={`/stations/${s.station_id}/intel`} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-500">
          Station Intelligence →
        </Link>
        <Link to="/stations" className="ml-auto text-sm text-blue-500 hover:underline">← All stations</Link>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Stat label="Health" value={health.data ? `${health.data.overall.toFixed(0)}/100` : '—'} sub={health.data ? `worst: ${health.data.worst_sensor}` : 'computing…'} />
        <Stat label="Readings" value={(obs.data ?? []).length} sub={`last ${limit} shown`} />
        <Stat label="Anomalies" value={(anomalies.data ?? []).length} sub="recent 20" />
        <Stat
          label="Latest temp"
          value={obs.data?.length ? `${obs.data[0].temperature.toFixed(1)}°C` : '—'}
          sub={obs.data?.length ? formatTs(obs.data[0].timestamp) : ''}
        />
      </div>

      <Card
        title="Observations"
        subtitle="Live readings from the backend"
        action={
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className={inputCls}>
            {[50, 100, 200, 500].map((n) => (
              <option key={n} value={n}>last {n}</option>
            ))}
          </select>
        }
      >
        {series.length === 0 ? (
          <EmptyState message="No observations yet for this station." />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={series}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="t" tick={false} />
              <YAxis yAxisId="t" orientation="left" />
              <YAxis yAxisId="p" orientation="right" hide />
              <Tooltip />
              <Legend />
              <Line yAxisId="t" type="monotone" dataKey="temp" name="Temp °C" stroke="#ef4444" dot={false} strokeWidth={2} />
              <Line yAxisId="t" type="monotone" dataKey="hum" name="Hum %" stroke="#3b82f6" dot={false} />
              <Line yAxisId="p" type="monotone" dataKey="press" name="Press hPa" stroke="#22c55e" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      {health.data && health.data.trend.length > 0 && (
        <Card title="Health trend" subtitle="Trailing-window overall score per day">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={health.data.trend.map((t) => ({ ...t, score: Number(t.score.toFixed(1)) }))}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#8b5cf6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <Card title="Recent anomalies" subtitle="Flagged by the hybrid engine">
        {(anomalies.data ?? []).length === 0 ? (
          <EmptyState message="No anomalies for this station." />
        ) : (
          <DataTable
            columns={[
              { header: 'Time', render: (a) => <span className="whitespace-nowrap">{formatTs(a.timestamp)}</span> },
              { header: 'Type', render: (a) => <span className="text-xs">{a.root_cause}</span> },
              { header: 'Score', render: (a) => <span className="font-bold">{a.score.toFixed(0)}</span> },
              { header: 'Severity', render: (a) => <StatusBadge value={a.severity} /> },
              { header: '', render: (a) => <button className={btnGhost} onClick={() => navigate(`/anomalies/${a.id}`)}>Why?</button> },
            ]}
            rows={anomalies.data ?? []}
            rowKey={(a) => a.id}
          />
        )}
      </Card>
    </div>
  );
}
