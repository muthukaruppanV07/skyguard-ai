import { useState } from 'react';
import { usePoll } from '../hooks';
import { maintenanceApi } from '../api/client';
import { Card, EmptyState, ErrorState, Loading, StatusBadge, btnPrimary } from '../components/ui';

export default function Maintenance() {
  const [busy, setBusy] = useState<string | null>(null);
  const list = usePoll(() => maintenanceApi.list(), 30000);

  const sync = async (id: string) => {
    setBusy(id);
    try {
      await maintenanceApi.sync(id);
      list.refresh();
    } catch {
      /* surfaced on next poll */
    } finally {
      setBusy(null);
    }
  };

  if (list.error) return <div className="p-4"><ErrorState message={list.error} onRetry={list.refresh} /></div>;
  if (!list.data) return <div className="p-4"><Loading /></div>;

  return (
    <div className="page-enter space-y-4 p-4">
      {[...list.data].sort((a, b) => b.worst_risk - a.worst_risk).map((st) => (
        <Card
          key={st.station_id}
          title={`${st.station_id} — worst risk ${st.worst_risk.toFixed(0)} (${st.worst_sensor})`}
          subtitle={`${st.open_orders.length} open work orders`}
          action={
            <button disabled={busy === st.station_id} className={btnPrimary} onClick={() => sync(st.station_id)}>
              {busy === st.station_id ? 'Syncing…' : 'Recompute + sync orders'}
            </button>
          }
        >
          <div className="space-y-3">
            {st.sensors.map((s) => (
              <div key={s.sensor_type} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-bold">{s.sensor_type}</span>
                  <StatusBadge value={s.risk_level} />
                  <span className="text-xs">priority {s.maintenance_priority}</span>
                  <span className="text-xs tabular-nums text-slate-500">
                    risk {s.maintenance_risk.toFixed(0)}/100 · health {s.health.toFixed(0)}
                  </span>
                </div>
                <p className="mt-1 text-sm">{s.reason}</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-600 dark:text-slate-300">
                  {s.recommended_action.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            ))}
            {st.open_orders.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Open work orders</p>
                <ul className="mt-1 space-y-1 text-sm">
                  {st.open_orders.map((o) => (
                    <li key={o.id} className="flex gap-2">
                      <StatusBadge value={o.priority} />
                      <span className="flex-1">{o.recommendation}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {st.sensors.every((s) => s.maintenance_priority === 'LOW') && (
              <EmptyState message="No degradation trends — no work orders needed." />
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}
