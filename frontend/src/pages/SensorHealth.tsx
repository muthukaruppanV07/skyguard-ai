import { useNavigate } from 'react-router-dom';
import { usePoll } from '../hooks';
import { sensorHealthApi } from '../api/client';
import { Card, DataTable, ErrorState, Loading, StatusBadge } from '../components/ui';

export default function SensorHealth() {
  const navigate = useNavigate();
  const overview = usePoll(() => sensorHealthApi.overview(), 30000);

  if (overview.error) return <div className="p-4"><ErrorState message={overview.error} onRetry={overview.refresh} /></div>;
  if (!overview.data) return <div className="p-4"><Loading /></div>;

  const counts: Record<string, number> = {};
  for (const h of overview.data) counts[h.status] = (counts[h.status] ?? 0) + 1;

  return (
    <div className="page-enter space-y-4 p-4">
      <Card title="Fleet health" subtitle={Object.entries(counts).map(([k, v]) => `${v} ${k}`).join(' · ') || 'No stations'}>
        <DataTable
          columns={[
            { header: 'Station', render: (h) => <span className="font-semibold text-blue-500">{h.station_id}</span> },
            { header: 'Overall', render: (h) => <span className="font-bold">{h.overall.toFixed(0)}/100</span> },
            { header: 'Temp', render: (h) => <span>{h.sensors.find((s) => s.sensor_type === 'TEMPERATURE')?.score.toFixed(0) ?? '—'}</span> },
            { header: 'Press', render: (h) => <span>{h.sensors.find((s) => s.sensor_type === 'PRESSURE')?.score.toFixed(0) ?? '—'}</span> },
            { header: 'Hum', render: (h) => <span>{h.sensors.find((s) => s.sensor_type === 'HUMIDITY')?.score.toFixed(0) ?? '—'}</span> },
            { header: 'Worst', render: (h) => <span className="text-xs">{h.worst_sensor}</span> },
            { header: 'Status', render: (h) => <StatusBadge value={h.status} /> },
          ]}
          rows={[...overview.data].sort((a, b) => a.overall - b.overall)}
          rowKey={(h) => h.station_id}
          onRowClick={(h) => navigate(`/health/${h.station_id}`)}
        />
      </Card>
      <p className="text-xs text-slate-500">Scores derive from counted anomaly history, drift slopes, frozen runs and data gaps — recomputed on every ingest. Click a station for penalty breakdown and 14-day trend.</p>
    </div>
  );
}
