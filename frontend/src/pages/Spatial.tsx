import { useState } from 'react';
import { usePoll } from '../hooks';
import { sensorHealthApi, spatialApi, stationsApi } from '../api/client';
import { Card, DataTable, EmptyState, ErrorState, Loading, Stat, StatusBadge, btnGhost, inputCls } from '../components/ui';
import StationMap from '../components/StationMap';

const BAND_COLOR: Record<string, string> = { HIGH: '#22c55e', MEDIUM: '#facc15', LOW: '#ef4444', UNKNOWN: '#64748b' };

export default function Spatial() {
  const stations = usePoll(() => stationsApi.list(), 60000);
  const health = usePoll(() => sensorHealthApi.overview(), 30000);
  const [stationId, setStationId] = useState('');
  const [radius, setRadius] = useState('2000');
  const [k, setK] = useState('4');
  const [applied, setApplied] = useState({ radius: 2000, k: 4 });

  const activeId = stationId || stations.data?.[0]?.station_id || '';
  const intel = usePoll(
    () => (activeId ? spatialApi.station(activeId, { radius_km: applied.radius, k: applied.k }) : Promise.resolve(null)),
    30000,
    [activeId, applied.radius, applied.k],
  );

  const healthByStation: Record<string, string> = Object.fromEntries((health.data ?? []).map((h) => [h.station_id, h.status]));
  const apply = () => setApplied({ radius: Number(radius) || 2000, k: Number(k) || 4 });

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Spatial Intelligence"
        subtitle="Neighbor agreement, spatial deviation and regional consistency — live from backend readings"
        action={
          <div className="flex flex-wrap gap-2">
            <select value={activeId} onChange={(e) => setStationId(e.target.value)} className={inputCls}>
              {(stations.data ?? []).map((s) => (
                <option key={s.station_id} value={s.station_id}>{s.station_id} · {s.name}</option>
              ))}
            </select>
            <input value={radius} onChange={(e) => setRadius(e.target.value)} placeholder="radius km" title="Search radius (km)" className={`${inputCls} w-28`} />
            <input value={k} onChange={(e) => setK(e.target.value)} placeholder="k" title="Max neighbours" className={`${inputCls} w-20`} />
            <button className={btnGhost} onClick={apply}>Apply</button>
          </div>
        }
      >
        {!stations.data ? <Loading /> : (
          <StationMap stations={stations.data} healthByStation={healthByStation} searchQuery={activeId} height={380} />
        )}
      </Card>

      {intel.error && <ErrorState message={intel.error} onRetry={intel.refresh} />}
      {!intel.data ? <Loading label="Computing spatial intel…" /> : (
        <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Stat
              label="Neighbor agreement"
              value={intel.data.neighbor_agreement}
              sub={`${intel.data.neighbors.length} neighbours in range`}
              accent={BAND_COLOR[intel.data.neighbor_agreement]}
            />
            <Stat
              label="Spatial deviation"
              value={intel.data.spatial_deviation_c !== null ? `${intel.data.spatial_deviation_c >= 0 ? '+' : ''}${intel.data.spatial_deviation_c.toFixed(1)}°C` : '—'}
              sub={intel.data.spatial_z !== null ? `z = ${intel.data.spatial_z >= 0 ? '+' : ''}${intel.data.spatial_z.toFixed(1)} vs mean ${intel.data.neighbor_mean_c?.toFixed(1)}°C` : 'insufficient data'}
              accent={intel.data.neighbor_agreement === 'LOW' ? '#ef4444' : undefined}
            />
            <Stat
              label="Regional consistency"
              value={intel.data.regional_band}
              sub={intel.data.regional_consistency !== null ? `${(intel.data.regional_consistency * 100).toFixed(0)}% neighbours share the move` : 'needs neighbour histories'}
              accent={BAND_COLOR[intel.data.regional_band]}
            />
            <Stat label="Effect on verdict" value={intel.data.regional_band === 'HIGH' ? '→ WEATHER' : intel.data.neighbor_agreement === 'LOW' ? '→ FAULT' : '→ FUSION'} sub="classifier hint" />
          </div>

          <Card title="How this affects the verdict" subtitle="Same regional signal the classifier fuses">
            <p className="text-sm leading-relaxed">{intel.data.classification_hint}</p>
            {typeof intel.data.method?.scored_neighbours === 'number' && (
              <p className="mt-1 text-xs text-slate-500">
                Scored {String(intel.data.method.scored_neighbours)} neighbours, {String(intel.data.method.same_direction)} share the direction.
              </p>
            )}
          </Card>

          <Card title={`Neighbors of ${intel.data.station_id}`} subtitle="Deviation vs the neighbour-group mean; |dev| outliers highlighted">
            {intel.data.neighbors.length === 0 ? <EmptyState message="No neighbours with readings in range." /> : (
              <DataTable
                columns={[
                  { header: 'Station', render: (n) => <span className="font-semibold">{n.station_id}</span> },
                  { header: 'Name', render: (n) => <span className="text-xs">{n.name}</span> },
                  { header: 'Dist km', render: (n) => n.distance_km.toFixed(0) },
                  { header: 'Temp °C', render: (n) => <span className="font-bold">{n.temperature !== null ? n.temperature.toFixed(1) : '—'}</span> },
                  {
                    header: 'Deviation',
                    render: (n) =>
                      n.temp_deviation !== null ? (
                        <span className="font-bold" style={{ color: Math.abs(n.temp_deviation) > 4 ? '#ef4444' : undefined }}>
                          {n.temp_deviation >= 0 ? '+' : ''}{n.temp_deviation.toFixed(1)}°C
                        </span>
                      ) : (
                        <span>—</span>
                      ),
                  },
                ]}
                rows={intel.data.neighbors}
                rowKey={(n) => n.station_id}
              />
            )}
          </Card>
        </>
      )}
    </div>
  );
}
