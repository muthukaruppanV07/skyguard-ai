import { useState } from 'react';
import { systemApi } from '../api/client';
import { usePoll } from '../hooks';
import { Card, EmptyState, ErrorState, Loading, Stat, StatusBadge, btnPrimary } from '../components/ui';

const STAGE_LABELS: Record<string, string> = {
  gap_gate: 'GAP GATE',
  feature_engineering: 'FEATURE ENGINEERING',
  physical: 'PHYSICAL VALIDATION',
  statistical: 'STATISTICAL ANALYSIS',
  robust_z: 'ROBUST Z-SCORE',
  rate: 'RATE OF CHANGE',
  isolation_forest: 'ML DETECTION',
  temporal: 'TEMPORAL ANALYSIS',
  multivariate: 'MULTIVARIATE ANALYSIS',
  frozen: 'FROZEN SENSOR',
  drift: 'DRIFT',
  fusion: 'EVIDENCE FUSION',
  event_classification: 'EVENT CLASSIFICATION',
  false_alarm_guard: 'FALSE-ALARM GUARD',
  explanation: 'EXPLANATION',
  persistence: 'FINAL DECISION',
};

function fmtBytes(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)} kB`;
  return `${n} B`;
}

export default function Judge() {
  const [nonce, setNonce] = useState(0);
  const info = usePoll(() => systemApi.info(), null, [nonce]);

  const refresh = () => {
    setNonce((n) => n + 1);
    info.refresh();
  };
  const d = info.data;

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Judge mode — technical transparency"
        subtitle="Every value measured or counted live from this backend. Nothing staged."
        action={<button className={btnPrimary} onClick={refresh}>Re-measure now</button>}
      >
        {info.error && <ErrorState message={info.error} onRetry={refresh} />}
        {!info.data && !info.error && <Loading label="Probing live system (timing real detections)…" />}
        {d && (
          <p className="text-xs text-slate-500">
            Generated {new Date(d.generated_at).toLocaleString()} · environment {d.app.environment} ·
            latencies are means of {d.latency.runs} live runs{d.latency.station_id ? ` on ${d.latency.station_id}` : ''}.
          </p>
        )}
      </Card>

      {d && (
        <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Stat label="Model" value={d.app.name} sub={`v${d.app.version} · sklearn ${d.ml.sklearn.version ?? 'absent'}`} />
            <Stat
              label="Detection latency"
              value={d.latency.detection_latency_ms !== null ? `${d.latency.detection_latency_ms} ms` : 'n/a'}
              sub={d.latency.reason ?? `full pipeline · ${d.latency.runs} runs`}
            />
            <Stat
              label="Inference latency"
              value={d.latency.inference_latency_ms !== null ? `${d.latency.inference_latency_ms} ms` : 'n/a'}
              sub="IsolationForest fit + score"
            />
            <Stat
              label="Ingestion rate"
              value={`${d.ingestion.per_minute}/min`}
              sub={`${d.ingestion.observations_last_hour} obs last hour`}
            />
          </div>

          <Card title="Detection pipeline" subtitle="Execution order imported from the engine — the diagram cannot drift from code">
            <ol className="flex flex-col items-stretch gap-1">
              {d.pipeline.map((stage, i) => (
                <li key={`${stage}-${i}`} className="flex items-center gap-3">
                  <span className="w-8 shrink-0 text-right font-mono text-xs text-slate-500">{String(i + 1).padStart(2, '0')}</span>
                  <span className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-bold tracking-wide dark:border-slate-800 dark:bg-slate-800/60">
                    {STAGE_LABELS[stage] ?? stage.toUpperCase()}
                  </span>
                  {i < d.pipeline.length - 1 && <span className="sr-only">down arrow</span>}
                </li>
              ))}
            </ol>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Detection methods" subtitle="Fusion weights from live config">
              <ul className="space-y-1.5 text-sm tabular-nums">
                {d.detection_methods.map((d) => (
                  <li key={d.name} className="flex items-center gap-2">
                    <StatusBadge value={d.enabled ? 'NORMAL' : 'LOW'} />
                    <span className="flex-1 font-mono">{d.name}</span>
                    <span className="text-slate-500">w={d.weight ?? '—'}</span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Features" subtitle={`${d.features.count} engineered signals (T/P/H + time only)`}>
              <p className="max-h-64 overflow-y-auto font-mono text-xs leading-relaxed">{d.features.names.join(', ')}</p>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Dataset size" subtitle="Counted rows, this database">
              <div className="grid grid-cols-2 gap-2 text-sm tabular-nums">
                {Object.entries(d.dataset).map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                    <p className="text-[11px] uppercase text-slate-500">{k}</p>
                    <p className="text-lg font-bold">{v}</p>
                  </div>
                ))}
              </div>
            </Card>
            <Card title="Training status" subtitle="Artifacts on disk + inference mode">
              <ul className="space-y-1.5 text-sm">
                {d.models.map((m) => (
                  <li key={m.name} className="flex justify-between gap-2 tabular-nums">
                    <span className="font-mono">{m.artifact}</span>
                    <span className={m.present ? 'text-emerald-500' : 'text-red-500'}>
                      {m.present ? `present · ${fmtBytes(m.size_bytes ?? 0)} · ${m.modified?.slice(0, 10)}` : 'MISSING'}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs leading-relaxed text-slate-500">{d.ml.inference_mode}</p>
              <p className="mt-1 text-xs leading-relaxed">{d.training_status}</p>
            </Card>
          </div>

          <Card title="Subsystem status" subtitle="Probed now, not configured">
            <div className="grid gap-2 text-sm xl:grid-cols-4">
              <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-[11px] uppercase text-slate-500">API</p>
                <p className="font-bold text-emerald-500">{d.status.api.status.toUpperCase()} · v{d.status.api.version}</p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-[11px] uppercase text-slate-500">ML engine</p>
                <p className={`font-bold ${d.status.ml_engine.status === 'ready' ? 'text-emerald-500' : 'text-amber-500'}`}>
                  {d.status.ml_engine.status.toUpperCase()}
                </p>
                <p className="text-xs text-slate-500">IF ran in probe: {d.status.ml_engine.isolation_forest_ran_in_probe ? 'yes' : 'no'}</p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-[11px] uppercase text-slate-500">Database</p>
                <p className="font-bold text-emerald-500">{d.status.database.status.toUpperCase()}</p>
                <p className="text-xs tabular-nums text-slate-500">
                  {d.status.database.file ? `${fmtBytes(d.status.database.file.size_bytes)}` : 'embedded'}
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-[11px] uppercase text-slate-500">Streaming</p>
                <p className="font-bold">{d.status.streaming.status}</p>
                <p className="text-xs tabular-nums text-slate-500">
                  {d.status.streaming.tick !== undefined
                    ? `tick ${d.status.streaming.tick} · ${d.status.streaming.subscribers ?? 0} subscribers`
                    : d.status.streaming.reason ?? ''}
                </p>
              </div>
            </div>
          </Card>

          {d.models.some((m) => !m.present) && (
            <EmptyState message="One or more training artifacts are missing — statistical detectors carry the load; see training status." />
          )}
        </>
      )}
    </div>
  );
}
