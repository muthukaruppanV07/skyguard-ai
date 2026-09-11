import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { usePoll, formatTs } from '../hooks';
import { anomaliesApi, stationsApi } from '../api/client';
import { Card, DataTable, EmptyState, ErrorState, Loading, StatusBadge, inputCls, btnGhost } from '../components/ui';

export default function AnomalyCenter() {
  const navigate = useNavigate();
  const [station, setStation] = useState('');
  const [severity, setSeverity] = useState('');
  const [limit, setLimit] = useState(100);
  const anomalies = usePoll(() => anomaliesApi.list({ limit }), 15000, [limit]);
  const stations = usePoll(() => stationsApi.list(), 60000);

  const rows = useMemo(() => {
    return (anomalies.data ?? []).filter(
      (a) => (!station || a.station_id === station) && (!severity || a.severity === severity),
    );
  }, [anomalies.data, station, severity]);

  if (anomalies.error) return <div className="p-4"><ErrorState message={anomalies.error} onRetry={anomalies.refresh} /></div>;
  if (!anomalies.data) return <div className="p-4"><Loading /></div>;

  const byType: Record<string, number> = {};
  for (const a of anomalies.data) byType[a.root_cause] = (byType[a.root_cause] ?? 0) + 1;

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Anomaly Center"
        subtitle={`${rows.length} shown · every row links to its AI explanation`}
        action={
          <div className="flex flex-wrap gap-2">
            <select value={station} onChange={(e) => setStation(e.target.value)} className={inputCls}>
              <option value="">All stations</option>
              {(stations.data ?? []).map((s) => (
                <option key={s.station_id} value={s.station_id}>{s.station_id}</option>
              ))}
            </select>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} className={inputCls}>
              <option value="">All severities</option>
              {['LOW', 'SUSPICIOUS', 'HIGH', 'CRITICAL'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className={inputCls}>
              {[50, 100, 200, 500].map((n) => (
                <option key={n} value={n}>last {n}</option>
              ))}
            </select>
          </div>
        }
      >
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          {Object.entries(byType).map(([t, n]) => (
            <span key={t} className="rounded-full bg-slate-100 px-2.5 py-1 font-medium dark:bg-slate-800">
              {t}: {n}
            </span>
          ))}
        </div>
        {rows.length === 0 ? (
          <EmptyState message="No anomalies match the filters." />
        ) : (
          <DataTable
            columns={[
              { header: 'ID', render: (a) => <span className="text-slate-500">#{a.id}</span> },
              { header: 'Time', render: (a) => <span className="whitespace-nowrap">{formatTs(a.timestamp)}</span> },
              { header: 'Station', render: (a) => <Link className="font-semibold text-blue-500" to={`/stations/${a.station_id}`}>{a.station_id}</Link> },
              { header: 'Type', render: (a) => <span className="text-xs">{a.root_cause}</span> },
              { header: 'Score', render: (a) => <span className="font-bold">{a.score.toFixed(0)}</span> },
              { header: 'Conf', render: (a) => <span>{(a.confidence * 100).toFixed(0)}%</span> },
              { header: 'Severity', render: (a) => <StatusBadge value={a.severity} /> },
              { header: '', render: (a) => <button className={btnGhost} onClick={() => navigate(`/anomalies/${a.id}`)}>Explain</button> },
            ]}
            rows={rows}
            rowKey={(a) => a.id}
          />
        )}
      </Card>
    </div>
  );
}
