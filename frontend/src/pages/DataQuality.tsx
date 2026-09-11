import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { datasetApi, qualityApi, stationsApi } from '../api/client';
import { usePoll, formatTs } from '../hooks';
import { Card, DataTable, EmptyState, ErrorState, Loading, Stat, StatusBadge, btnGhost, btnPrimary, inputCls } from '../components/ui';
import { downloadFile } from '../hooks';

const DIMS = ['completeness', 'validity', 'consistency', 'timeliness', 'overall'] as const;
const PARAMS = ['TEMPERATURE', 'PRESSURE', 'HUMIDITY'];
const TIMES = [24, 72, 168, 720];

function scoreColor(v: number): string {
  return v >= 90 ? '#22c55e' : v >= 70 ? '#84cc16' : v >= 40 ? '#facc15' : '#ef4444';
}

function QualityOverview() {
  const overview = usePoll(() => qualityApi.overview(168), 60000);
  if (overview.error) return <ErrorState message={overview.error} onRetry={overview.refresh} />;
  if (!overview.data) return <Loading label="Computing quality dimensions…" />;
  const f = overview.data.fleet;
  const totalIssues = overview.data.total_issues;
  return (
    <>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        {DIMS.map((d) => (
          <Stat key={d} label={d.replace(/^\w/, (c) => c.toUpperCase())} value={`${f[d].toFixed(0)}/100`} accent={scoreColor(f[d])} sub={d === 'overall' ? `${totalIssues} open issues` : 'fleet mean'} />
        ))}
      </div>
      <Card title="Per-station quality" subtitle="All five dimensions, worst first">
        <DataTable
          columns={[
            { header: 'Station', render: (s) => <span className="font-semibold">{s.station_id}</span> },
            ...DIMS.map((d) => ({
              header: d.slice(0, 5),
              render: (s: (typeof overview.data.stations)[number]) => (
                <span className="font-bold" style={{ color: scoreColor(s[d]) }}>{s[d].toFixed(0)}</span>
              ),
            })),
            {
              header: 'Top issues',
              render: (s: (typeof overview.data.stations)[number]) =>
                Object.entries(s.counts).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([k, v]) => `${k}×${v}`).join(', ') || '—',
            },
          ]}
          rows={[...overview.data.stations].sort((a, b) => a.overall - b.overall)}
          rowKey={(s) => s.station_id}
        />
      </Card>
      {Object.keys(overview.data.issue_counts).length > 0 && (
        <Card title="Issue mix" subtitle="Fleet-wide counts by type">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={Object.entries(overview.data.issue_counts).map(([name, count]) => ({ name, count }))} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#f97316" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </>
  );
}

const ISSUE_TYPES = ['missing_values', 'invalid_values', 'duplicate_records', 'frozen_sensor', 'comm_gaps', 'spikes', 'drift', 'multivariate'];

function QualityIssues() {
  const stations = usePoll(() => stationsApi.list(), 60000);
  const [station, setStation] = useState('');
  const [parameter, setParameter] = useState('');
  const [hours, setHours] = useState(168);
  const [issueType, setIssueType] = useState('');
  const issues = usePoll(
    () => qualityApi.issues({
      station_id: station || undefined,
      parameter: parameter || undefined,
      hours,
      issue_type: issueType || undefined,
      limit: 200,
    }),
    30000,
    [station, parameter, hours, issueType],
  );

  return (
    <Card
      title="Issue explorer"
      subtitle={issues.data ? `${issues.data.total} issues match` : 'Filter by station, parameter, time and type'}
      action={
        <div className="flex flex-wrap gap-2">
          <select value={station} onChange={(e) => setStation(e.target.value)} className={inputCls}>
            <option value="">All stations</option>
            {(stations.data ?? []).map((s) => (
              <option key={s.station_id} value={s.station_id}>{s.station_id}</option>
            ))}
          </select>
          <select value={parameter} onChange={(e) => setParameter(e.target.value)} className={inputCls}>
            <option value="">All parameters</option>
            {PARAMS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))} className={inputCls}>
            {TIMES.map((h) => (
              <option key={h} value={h}>last {h}h</option>
            ))}
          </select>
          <select value={issueType} onChange={(e) => setIssueType(e.target.value)} className={inputCls}>
            <option value="">All issue types</option>
            {ISSUE_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      }
    >
      {issues.error && <ErrorState message={issues.error} onRetry={issues.refresh} />}
      {!issues.data ? <Loading /> : issues.data.issues.length === 0 ? (
        <EmptyState message="No issues match — clean window." />
      ) : (
        <DataTable
          columns={[
            { header: 'Time', render: (i) => <span className="whitespace-nowrap">{formatTs(i.timestamp)}</span> },
            { header: 'Station', render: (i) => <span className="font-semibold">{i.station_id}</span> },
            { header: 'Parameter', render: (i) => <span className="text-xs">{i.parameter}</span> },
            { header: 'Issue', render: (i) => <StatusBadge value={i.severity} /> },
            { header: 'Type', render: (i) => <span className="text-xs">{i.issue_type}</span> },
            { header: 'Detail', render: (i) => <span className="text-xs">{i.detail}</span> },
          ]}
            rows={issues.data.issues}
            rowKey={(i) => `${i.station_id}-${i.timestamp}-${i.issue_type}-${i.detail}`}
        />
      )}
    </Card>
  );
}

export default function DataQuality() {
  const [gen, setGen] = useState({ num_stations: 4, num_observations: 1000, sampling_interval_minutes: 60, anomaly_percentage: 5, seed: 42, ingest: false });
  const [genResult, setGenResult] = useState<unknown>(null);
  const [uploadResult, setUploadResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: string, v: number | boolean) => setGen((g) => ({ ...g, [k]: v }));

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await datasetApi.generate(gen);
      setGenResult(r);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err?.response?.data?.detail ?? err?.message ?? 'Generation failed');
    } finally {
      setBusy(false);
    }
  };

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const r = await datasetApi.upload(file);
      setUploadResult(r);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err?.response?.data?.detail ?? err?.message ?? 'Upload failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-enter space-y-4 p-4">
      {error && <ErrorState message={error} onRetry={() => setError(null)} />}
      <QualityOverview />
      <QualityIssues />
      <Card
        title="Synthetic dataset generator"
        subtitle="Physics-based T/P/H with labelled faults — same generator the backend uses"
        action={<button disabled={busy} className={btnPrimary} onClick={generate}>{busy ? 'Working…' : 'Generate'}</button>}
      >
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-6">
          {[
            ['num_stations', 'Stations (1–8)'],
            ['num_observations', 'Observations'],
            ['sampling_interval_minutes', 'Interval (min)'],
            ['anomaly_percentage', 'Anomaly %'],
            ['seed', 'Seed'],
          ].map(([k, label]) => (
            <label key={k} className="text-xs">{label}
              <input
                type="number"
                value={Number(gen[k as keyof typeof gen])}
                onChange={(e) => set(k, Number(e.target.value))}
                className={`${inputCls} mt-1 w-full`}
              />
            </label>
          ))}
          <label className="flex items-end gap-2 pb-2 text-xs">
            <input type="checkbox" checked={gen.ingest} onChange={(e) => set('ingest', e.target.checked)} />
            Ingest clean rows to DB
          </label>
        </div>
        {genResult !== null && (
          <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-emerald-300 dark:bg-black">
            {JSON.stringify(genResult, null, 2)}
          </pre>
        )}
      </Card>

      <Card title="CSV upload" subtitle="Format: timestamp,station_id,latitude,longitude,temperature,pressure,humidity">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="file"
            accept=".csv"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
              e.target.value = '';
            }}
            className="text-sm"
          />
          <a href={datasetApi.templateUrl()} className={btnGhost}>Download template</a>
          <button
            className={btnGhost}
            onClick={() =>
              downloadFile(
                'aws_template.csv',
                'timestamp,station_id,latitude,longitude,temperature,pressure,humidity\n2026-01-01T00:00:00+00:00,AWS001,28.6139,77.2090,31.5,1005.2,62.0\n',
                'text/csv',
              )
            }
          >
            Copy local template
          </button>
        </div>
        {uploadResult !== null && (
          <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-emerald-300 dark:bg-black">
            {JSON.stringify(uploadResult, null, 2)}
          </pre>
        )}
      </Card>
    </div>
  );
}
