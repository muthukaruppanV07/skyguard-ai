import { useNavigate } from 'react-router-dom';
import { usePoll } from '../hooks';
import { sensorHealthApi, stationsApi } from '../api/client';
import { Card, DataTable, ErrorState, Loading, StatusBadge } from '../components/ui';
import StationMap from '../components/StationMap';

export default function Stations() {
  const navigate = useNavigate();
  const stations = usePoll(() => stationsApi.list(), 60000);
  const health = usePoll(() => sensorHealthApi.overview(), 30000);

  if (stations.error) return <div className="p-4"><ErrorState message={stations.error} onRetry={stations.refresh} /></div>;
  if (!stations.data) return <div className="p-4"><Loading /></div>;

  const healthByStation: Record<string, string> = Object.fromEntries((health.data ?? []).map((h) => [h.station_id, h.status]));
  const overallByStation: Record<string, number> = Object.fromEntries((health.data ?? []).map((h) => [h.station_id, h.overall]));

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Station network"
        subtitle={`${stations.data.length} automatic weather stations · click a marker for its popup`}
        action={<button className="text-xs font-semibold text-blue-500 hover:underline" onClick={() => navigate('/spatial')}>Spatial intelligence →</button>}
      >
        <StationMap stations={stations.data} healthByStation={healthByStation} />
      </Card>
      <Card title="All stations" subtitle="Click a row for observations, health trend and anomalies">
        <DataTable
          columns={[
            { header: 'ID', render: (s) => <span className="font-semibold text-blue-500">{s.station_id}</span> },
            { header: 'Name', render: (s) => s.name },
            { header: 'Lat', render: (s) => s.latitude.toFixed(2) },
            { header: 'Lon', render: (s) => s.longitude.toFixed(2) },
            {
              header: 'Health',
              render: (s) =>
                overallByStation[s.station_id] !== undefined ? (
                  <span className="font-bold">{overallByStation[s.station_id].toFixed(0)}/100</span>
                ) : (
                  <span className="text-slate-400">—</span>
                ),
            },
            {
              header: 'Status',
              render: (s) => <StatusBadge value={healthByStation[s.station_id] ?? s.status} />,
            },
          ]}
          rows={stations.data}
          rowKey={(s) => s.station_id}
          onRowClick={(s) => navigate(`/stations/${s.station_id}`)}
        />
      </Card>
    </div>
  );
}
