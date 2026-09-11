import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePoll } from '../hooks';
import { anomaliesApi, explainApi, insightsApi, stationsApi } from '../api/client';
import type { Explanation } from '../types';
import { Card, EmptyState, ErrorState, Loading, StatusBadge, btnPrimary, inputCls } from '../components/ui';

function ExplanationView({ exp }: { exp: Explanation }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge value={exp.severity} />
        <span className="text-sm font-semibold">{exp.anomaly_type}</span>
        <span className="text-sm tabular-nums">score {exp.anomaly_score.toFixed(0)}</span>
        {exp.event_type && <span className="text-xs">{exp.event_type}</span>}
      </div>
      <p className="rounded-lg bg-blue-500/10 p-3 text-sm font-medium leading-relaxed">{exp.main_reason}</p>
      <p className="text-sm font-semibold">{exp.conclusion}</p>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {exp.supporting_evidence.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
      <p className="text-sm"><span className="font-semibold">Action: </span>{exp.recommended_action}</p>
    </div>
  );
}

export default function AIInsights() {
  const navigate = useNavigate();
  const stations = usePoll(() => stationsApi.list(), 60000);
  const [form, setForm] = useState({ station_id: 'AWS001', timestamp: '', temperature: '', pressure: '', humidity: '' });
  const [result, setResult] = useState<Explanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const recent = usePoll(() => anomaliesApi.list({ limit: 5 }), 30000);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const [hours, setHours] = useState(24);
  const feed = usePoll(() => insightsApi.list(hours), 60000, [hours]);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const exp = await explainApi.preview({
        station_id: form.station_id,
        timestamp: form.timestamp ? new Date(form.timestamp).toISOString() : new Date().toISOString(),
        temperature: form.temperature === '' ? null : Number(form.temperature),
        pressure: form.pressure === '' ? null : Number(form.pressure),
        humidity: form.humidity === '' ? null : Number(form.humidity),
      });
      setResult(exp);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err?.response?.data?.detail ?? err?.message ?? 'Preview failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Fleet insights"
        subtitle="Generated from live readings, anomaly history and health — every claim cites its evidence"
        action={
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))} className={inputCls}>
            {[6, 24, 72, 168].map((h) => (
              <option key={h} value={h}>last {h}h</option>
            ))}
          </select>
        }
      >
        {feed.error && <ErrorState message={feed.error} onRetry={feed.refresh} />}
        {feed.loading && !feed.data && <Loading label="Mining live data…" />}
        {(feed.data ?? []).length === 0 && !feed.loading && (
          <EmptyState message="No insights in this window — the fleet looks unremarkable." />
        )}
        <div className="space-y-3">
          {(feed.data ?? []).map((ins) => (
            <article key={ins.id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge value={ins.severity === 'ACT' ? 'CRITICAL' : ins.severity === 'WATCH' ? 'SUSPICIOUS' : 'NORMAL'} />
                <h3 className="flex-1 text-sm font-bold">{ins.title}</h3>
                <span className="text-xs tabular-nums text-slate-500">confidence {(ins.confidence * 100).toFixed(0)}%</span>
              </div>
              <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                <span className="block h-full rounded-full bg-blue-500" style={{ width: `${ins.confidence * 100}%` }} />
              </span>
              <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-slate-600 dark:text-slate-300">
                {ins.evidence.map((e, i) => (
                  <li key={i} className="tabular-nums">{e}</li>
                ))}
              </ul>
              {ins.affected_stations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {ins.affected_stations.map((s) => (
                    <button key={s} onClick={() => navigate(`/stations/${s}/intel`)} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-blue-500 hover:underline dark:bg-slate-800">
                      {s}
                    </button>
                  ))}
                </div>
              )}
              <p className="mt-2 text-sm"><span className="font-semibold">Action: </span>{ins.recommended_action}</p>
            </article>
          ))}
        </div>
      </Card>

      <Card
        title="What-if analyzer"
        subtitle="Run any hypothetical reading through the real engine + classifier + explainer. Nothing is stored."
        action={<button disabled={busy} className={btnPrimary} onClick={run}>{busy ? 'Analyzing…' : 'Analyze'}</button>}
      >
        {error && <ErrorState message={error} onRetry={run} />}
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-5">
          <label className="text-xs">Station
            <select value={form.station_id} onChange={(e) => set('station_id', e.target.value)} className={`${inputCls} mt-1 w-full`}>
              {(stations.data ?? []).map((s) => (
                <option key={s.station_id} value={s.station_id}>{s.station_id}</option>
              ))}
            </select>
          </label>
          <label className="text-xs">Timestamp
            <input type="datetime-local" value={form.timestamp} onChange={(e) => set('timestamp', e.target.value)} className={`${inputCls} mt-1 w-full`} />
          </label>
          <label className="text-xs">Temp °C
            <input value={form.temperature} onChange={(e) => set('temperature', e.target.value)} placeholder="31.5" className={`${inputCls} mt-1 w-full`} />
          </label>
          <label className="text-xs">Pressure hPa
            <input value={form.pressure} onChange={(e) => set('pressure', e.target.value)} placeholder="1005" className={`${inputCls} mt-1 w-full`} />
          </label>
          <label className="text-xs">Humidity %
            <input value={form.humidity} onChange={(e) => set('humidity', e.target.value)} placeholder="62" className={`${inputCls} mt-1 w-full`} />
          </label>
        </div>
        <div className="mt-3">
          {result ? <ExplanationView exp={result} /> : <EmptyState message="Enter a reading and press Analyze." />}
        </div>
      </Card>

      <Card title="How to trigger each verdict" subtitle="Try these against live history">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Sudden +12°C on one station → TEMPERATURE_SPIKE, probable sensor fault.</li>
          <li>Same +12°C with humidity/pressure dropped coherently on all neighbours → probable weather event.</li>
          <li>Identical values 8+ times → FROZEN_SENSOR.</li>
          <li>Blank fields → MISSING_DATA / COMMUNICATION_FAILURE path.</li>
        </ul>
      </Card>

      {(recent.data ?? []).length > 0 && (
        <Card title="Fresh from the engine" subtitle="Latest flagged anomalies — open for full why">
          <ul className="space-y-1 text-sm">
            {(recent.data ?? []).map((a) => (
              <li key={a.id}>
                <button className="text-blue-500 hover:underline" onClick={() => navigate(`/anomalies/${a.id}`)}>
                  #{a.id} {a.station_id} · {a.root_cause} · {a.score.toFixed(0)}
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
