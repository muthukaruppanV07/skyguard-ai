import { Link, useParams } from 'react-router-dom';
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { usePoll } from '../hooks';
import { sensorHealthApi } from '../api/client';
import { Card, ErrorState, Loading, StatusBadge } from '../components/ui';

export default function SensorHealthDetail() {
  const { stationId = '' } = useParams();
  const detail = usePoll(() => sensorHealthApi.detail(stationId), 30000, [stationId]);
  if (detail.error) return <div className="p-4"><ErrorState message={detail.error} onRetry={detail.refresh} /></div>;
  if (!detail.data) return <div className="p-4"><Loading /></div>;
  const d = detail.data;
  return (
    <div className="page-enter space-y-4 p-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">{d.station_id} health</h1>
        <StatusBadge value={d.status} />
        <span className="text-lg font-bold tabular-nums">{d.overall.toFixed(0)}/100</span>
        <Link to="/health" className="ml-auto text-sm text-blue-500 hover:underline">← Fleet</Link>
      </div>
      {d.sensors.map((s) => (
        <Card key={s.sensor_type} title={`${s.sensor_type} — ${s.score.toFixed(0)}/100`} subtitle={`${s.anomaly_count} anomalies in window`} action={<StatusBadge value={s.status} />}>
          <div className="grid grid-cols-2 gap-2 text-sm xl:grid-cols-4">
            {Object.entries(s.penalties).map(([k, v]) => (
              <div key={k} className="flex justify-between rounded-lg bg-slate-50 px-3 py-1.5 tabular-nums dark:bg-slate-800/60">
                <span className="text-xs">{k.replace(/_/g, ' ')}</span>
                <span className={`font-bold ${v > 0 ? 'text-amber-500' : 'text-emerald-500'}`}>−{Number(v).toFixed(1)}</span>
              </div>
            ))}
          </div>
        </Card>
      ))}
      {d.trend.length > 0 && (
        <Card title="14-day trend" subtitle="Trailing-window overall, recomputed daily">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={d.trend}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#8b5cf6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
