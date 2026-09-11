import { useState } from 'react';
import { usePoll } from '../hooks';
import { simApi, stationsApi } from '../api/client';
import { Card, ErrorState, Loading, StatusBadge, btnGhost, btnPrimary, inputCls } from '../components/ui';

export default function Simulation() {
  const status = usePoll(() => simApi.status(), 3000);
  const scenarios = usePoll(() => simApi.scenarios(), 60000);
  const stations = usePoll(() => stationsApi.list(), 60000);
  const [form, setForm] = useState({ scenario_id: 'temp_spike', station_ids: '', duration_ticks: '3', magnitude: '1' });
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastTick, setLastTick] = useState<unknown>(null);

  const run = async (fn: () => Promise<unknown>, label: string) => {
    setBusy(true);
    try {
      const r = await fn();
      setLastTick(r);
      setMsg(label);
      status.refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setMsg(`Failed: ${err?.response?.data?.detail ?? err?.message}`);
    } finally {
      setBusy(false);
    }
  };

  const inject = () =>
    run(
      () =>
        simApi.inject({
          scenario_id: form.scenario_id,
          station_ids: form.station_ids ? form.station_ids.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
          duration_ticks: Number(form.duration_ticks) || undefined,
          magnitude: Number(form.magnitude) || 1,
        }),
      `Injected ${form.scenario_id}`,
    );

  if (status.error) return <div className="p-4"><ErrorState message={status.error} onRetry={status.refresh} /></div>;
  if (!status.data) return <div className="p-4"><Loading label="Contacting simulation engine…" /></div>;
  const st = status.data;

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Engine controls"
        subtitle={`State: ${st.status} · Tick #${st.tick} · Scenario: ${st.scenario ?? 'none'}`}
        action={<StatusBadge value={st.status === 'RUNNING' ? 'HIGH' : 'NORMAL'} pulse={st.status === 'RUNNING'} />}
      >
        <div className="flex flex-wrap gap-2">
          <button disabled={busy} className={btnPrimary} onClick={() => run(() => simApi.start(), 'Streaming started')}>Start</button>
          <button disabled={busy} className={btnGhost} onClick={() => run(() => simApi.pause(), 'Paused')}>Pause</button>
          <button disabled={busy} className={btnGhost} onClick={() => run(() => simApi.resume(), 'Resumed')}>Resume</button>
          <button disabled={busy} className={btnGhost} onClick={() => run(() => simApi.stop(), 'Stopped')}>Stop</button>
          <button disabled={busy} className={btnGhost} onClick={() => run(() => simApi.reset(), 'Reset to tick 0')}>Reset</button>
          <button disabled={busy} className={btnGhost} onClick={() => run(() => simApi.tick(), 'Advanced one tick')}>Single tick</button>
        </div>
        {msg && <p className="mt-2 text-sm text-slate-500">{msg}</p>}
      </Card>

      <Card title="Inject scenario" subtitle="Fault programs run against the real detection pipeline" action={<button disabled={busy} className={btnPrimary} onClick={inject}>Inject</button>}>
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          <label className="text-xs">Scenario
            <select value={form.scenario_id} onChange={(e) => setForm({ ...form, scenario_id: e.target.value })} className={`${inputCls} mt-1 w-full`}>
              {(scenarios.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.id}</option>
              ))}
            </select>
          </label>
          <label className="text-xs">Stations (comma list, empty = default)
            <input value={form.station_ids} onChange={(e) => setForm({ ...form, station_ids: e.target.value })} placeholder="AWS001" className={`${inputCls} mt-1 w-full`} />
          </label>
          <label className="text-xs">Duration (ticks)
            <input value={form.duration_ticks} onChange={(e) => setForm({ ...form, duration_ticks: e.target.value })} className={`${inputCls} mt-1 w-full`} />
          </label>
          <label className="text-xs">Magnitude (0.1–5)
            <input value={form.magnitude} onChange={(e) => setForm({ ...form, magnitude: e.target.value })} className={`${inputCls} mt-1 w-full`} />
          </label>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Available: {(scenarios.data ?? []).map((s) => s.id).join(', ')} · Stations: {(stations.data ?? []).map((s) => s.station_id).join(', ')}
        </p>
        {lastTick !== null && (
          <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-emerald-300 dark:bg-black">
            {JSON.stringify(lastTick, null, 2)}
          </pre>
        )}
      </Card>
    </div>
  );
}
