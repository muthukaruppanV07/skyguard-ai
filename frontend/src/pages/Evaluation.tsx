import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { evalApi } from '../api/client';
import { usePoll } from '../hooks';
import type { EvalRun } from '../types';
import { Card, DataTable, EmptyState, ErrorState, Stat, btnPrimary, inputCls } from '../components/ui';

const METRICS = ['accuracy', 'precision', 'recall', 'f1', 'fpr'] as const;

function Confusion({ title, cm, accent }: { title: string; cm: EvalRun['methods']['hybrid']['confusion']; accent: string }) {
  const cells: [string, number][] = [['TP', cm.tp], ['FP', cm.fp], ['FN', cm.fn], ['TN', cm.tn]];
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</p>
      <div className="grid grid-cols-2 gap-1 text-center text-sm tabular-nums">
        {cells.map(([k, v]) => (
          <div key={k} className="rounded-lg bg-slate-50 px-2 py-1.5 dark:bg-slate-800/60" style={k === 'TP' ? { outline: `2px solid ${accent}` } : undefined}>
            <span className="font-bold">{k}</span> {v}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Evaluation() {
  const [form, setForm] = useState({ episodes_per_category: 2, history_points: 64, test_points: 12, seed: 42 });
  const [result, setResult] = useState<EvalRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const latest = usePoll(() => evalApi.latest().catch(() => null), null, []);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await evalApi.run(form);
      setResult(r);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err?.response?.data?.detail ?? err?.message ?? 'Run failed');
    } finally {
      setBusy(false);
    }
  };

  const view = result ?? latest.data ?? null;
  const set = (k: string, v: number) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Controlled evaluation"
        subtitle="Labeled episodes per fault category · traditional threshold QC vs SkyGuard hybrid AI · everything computed live"
        action={<button disabled={busy} className={btnPrimary} onClick={run}>{busy ? 'Running (≈1 min)…' : 'Run evaluation'}</button>}
      >
        {error && <ErrorState message={error} onRetry={run} />}
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          {[
            ['episodes_per_category', 'Episodes / category (1–5)'],
            ['history_points', 'History points'],
            ['test_points', 'Test points'],
            ['seed', 'Seed'],
          ].map(([k, label]) => (
            <label key={k} className="text-xs">{label}
              <input type="number" value={Number(form[k as keyof typeof form])} onChange={(e) => set(k, Number(e.target.value))} className={`${inputCls} mt-1 w-full`} />
            </label>
          ))}
        </div>
        {!view && !busy && <div className="mt-3"><EmptyState message="No run yet — configure and press Run evaluation." /></div>}
      </Card>

      {view && (
        <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Stat label="Hybrid F1" value={view.methods.hybrid.f1.toFixed(3)} sub={`threshold ${view.methods.threshold.f1.toFixed(3)}`} accent="#22c55e" />
            <Stat label="Hybrid recall" value={view.methods.hybrid.recall.toFixed(3)} sub={`threshold ${view.methods.threshold.recall.toFixed(3)}`} />
            <Stat label="Hybrid FPR" value={view.methods.hybrid.fpr.toFixed(3)} sub={`threshold ${view.methods.threshold.fpr.toFixed(3)}`} accent={view.methods.hybrid.fpr <= view.methods.threshold.fpr ? '#22c55e' : '#f97316'} />
            <Stat
              label="Mean latency"
              value={view.latency.hybrid.mean_steps !== null ? `${view.latency.hybrid.mean_steps} steps` : '—'}
              sub={`threshold ${view.latency.threshold.mean_steps ?? '—'} · ${view.episodes} episodes · seed ${view.config.seed}`}
            />
          </div>

          <Card title="Threshold vs hybrid" subtitle="Higher is better, except FPR (lower is better)">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={METRICS.map((m) => ({ metric: m.toUpperCase(), threshold: view.methods.threshold[m], hybrid: view.methods.hybrid[m] }))}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="metric" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 1]} />
                <Tooltip />
                <Legend />
                <Bar dataKey="threshold" name="Traditional threshold" fill="#64748b" />
                <Bar dataKey="hybrid" name="SkyGuard hybrid AI" fill="#22c55e" />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-3 grid gap-4 xl:grid-cols-2">
              <Confusion title="Threshold confusion" cm={view.methods.threshold.confusion} accent="#64748b" />
              <Confusion title="Hybrid confusion" cm={view.methods.hybrid.confusion} accent="#22c55e" />
            </div>
          </Card>

          <Card title="Per-category F1" subtitle="Spike · frozen · drift · missing · multivariate · spatial · sensor fault · weather · normal">
            <ResponsiveContainer width="100%" height={Math.max(220, Object.keys(view.categories).length * 34)}>
              <BarChart data={Object.entries(view.categories).map(([name, c]) => ({ name, threshold: c.threshold.f1, hybrid: c.hybrid.f1, n: c.n }))} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis type="number" domain={[0, 1]} />
                <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="threshold" name="Threshold" fill="#64748b" />
                <Bar dataKey="hybrid" name="Hybrid" fill="#22c55e" />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title="Per-category recall + latency" subtitle="Detection latency in steps from fault onset (mean over detected episodes)">
            <DataTable
              columns={[
                { header: 'Category', render: (r) => <span className="font-semibold">{r.name}</span> },
                { header: 'Thr recall', render: (r) => <span>{r.threshold.recall.toFixed(2)}</span> },
                { header: 'Hyb recall', render: (r) => <span className="font-bold">{r.hybrid.recall.toFixed(2)}</span> },
                { header: 'Thr F1', render: (r) => <span>{r.threshold.f1.toFixed(2)}</span> },
                { header: 'Hyb F1', render: (r) => <span className="font-bold">{r.hybrid.f1.toFixed(2)}</span> },
                { header: 'n', render: (r) => <span>{r.n}</span> },
              ]}
              rows={Object.entries(view.categories).map(([name, c]) => ({ name, ...c }))}
              rowKey={(r) => r.name}
            />
            <div className="mt-2 grid gap-2 text-sm tabular-nums xl:grid-cols-2">
              <p>Threshold latency: <b>{view.latency.threshold.mean_steps ?? '—'} steps</b> ({view.latency.threshold.detected_episodes}/{view.latency.threshold.total_episodes} episodes detected)</p>
              <p>Hybrid latency: <b>{view.latency.hybrid.mean_steps ?? '—'} steps</b> ({view.latency.hybrid.detected_episodes}/{view.latency.hybrid.total_episodes} episodes detected)</p>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
