import { useState } from 'react';
import { usePoll, formatTs, downloadFile } from '../hooks';
import { reportsApi, stationsApi } from '../api/client';
import type { Report, ReportSection } from '../types';
import { Card, DataTable, EmptyState, ErrorState, btnPrimary, btnGhost, inputCls } from '../components/ui';

function SectionView({ s }: { s: ReportSection }) {
  if (s.kind === 'kpi') {
    return (
      <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
        <p className="text-[11px] uppercase tracking-wider text-slate-500">{s.label}</p>
        <p className="text-lg font-bold tabular-nums">{String(s.value ?? '—')}</p>
      </div>
    );
  }
  if (s.kind === 'table') {
    const cols = s.columns ?? [];
    const rows = (s.rows ?? []) as (string | number | null)[][];
    if (!rows.length) return <EmptyState message="No rows in this window." />;
    return (
      <DataTable
        columns={cols.map((c) => ({ header: c, render: (r: (string | number | null)[]) => <span>{r[cols.indexOf(c)] ?? '—'}</span> }))}
        rows={rows}
        rowKey={(r) => JSON.stringify(r)}
      />
    );
  }
  if (s.kind === 'trends') {
    const trends = (s as { trends: Record<string, { date: string; score: number }[]> }).trends ?? {};
    const names = Object.keys(trends);
    if (!names.length) return <EmptyState message="No trend data." />;
    return (
      <div className="grid gap-2 text-xs tabular-nums xl:grid-cols-2">
        {names.map((n) => {
          const pts = trends[n];
          const first = pts[0]?.score;
          const last = pts[pts.length - 1]?.score;
          return (
            <div key={n} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
              <span className="font-bold">{n}</span>
              <span className="ml-2 text-slate-500">{pts.length} pts · {first?.toFixed(0)} → {last?.toFixed(0)}</span>
            </div>
          );
        })}
      </div>
    );
  }
  return null;
}

function ReportView({ report }: { report: Report }) {
  const kpis = report.sections.filter((s) => s.kind === 'kpi');
  const rest = report.sections.filter((s) => s.kind !== 'kpi');
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold">{report.title}</h2>
        <p className="text-sm text-slate-500">{report.summary}</p>
      </div>
      {kpis.length > 0 && (
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          {kpis.map((s, i) => (
            <SectionView key={i} s={s} />
          ))}
        </div>
      )}
      {rest.map((s, i) => (
        <div key={i}>
          <SectionView s={s} />
        </div>
      ))}
    </div>
  );
}

export default function Reports() {
  const stations = usePoll(() => stationsApi.list(), 60000);
  const [reportType, setReportType] = useState('daily_quality');
  const [stationId, setStationId] = useState('');
  const [days, setDays] = useState(7);
  const [preview, setPreview] = useState<Report | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const runs = usePoll(() => reportsApi.runs(20), 30000);

  const params = { report_type: reportType, station_id: stationId || null, days };

  const doPreview = async () => {
    setBusy(true);
    setError(null);
    try {
      setPreview(await reportsApi.preview(params));
      setRunId(null);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err?.response?.data?.detail ?? err?.message ?? 'Preview failed');
    } finally {
      setBusy(false);
    }
  };

  const doGenerate = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await reportsApi.generate(params);
      setPreview(r.report);
      setRunId(r.id);
      runs.refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err?.response?.data?.detail ?? err?.message ?? 'Generate failed');
    } finally {
      setBusy(false);
    }
  };

  const openRun = async (id: number) => {
    setBusy(true);
    try {
      const r = await reportsApi.get(id);
      setPreview(r.report);
      setRunId(r.id);
    } finally {
      setBusy(false);
    }
  };

  const exportBlob = async (format: 'json' | 'csv') => {
    if (runId === null) return;
    const res = await fetch(reportsApi.exportUrl(runId, format));
    if (!res.ok) {
      setError(`Export failed: ${res.status}`);
      return;
    }
    downloadFile(`report-${runId}.${format}`, await res.text(), format === 'csv' ? 'text/csv' : 'application/json');
  };

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Reports"
        subtitle="Five operational reports from live backend data — preview, persist, export"
        action={
          <div className="flex flex-wrap gap-2">
            <button disabled={busy} className={btnGhost} onClick={doPreview}>Preview</button>
            <button disabled={busy} className={btnPrimary} onClick={doGenerate}>{busy ? 'Working…' : 'Generate'}</button>
            <button disabled={runId === null} className={btnGhost} onClick={() => exportBlob('json')}>Export JSON</button>
            <button disabled={runId === null} className={btnGhost} onClick={() => exportBlob('csv')}>Export CSV</button>
            <button className={btnGhost} onClick={() => window.print()}>Print</button>
          </div>
        }
      >
        {error && <ErrorState message={error} onRetry={() => setError(null)} />}
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          <label className="text-xs">Report type
            <select value={reportType} onChange={(e) => setReportType(e.target.value)} className={`${inputCls} mt-1 w-full`}>
              <option value="daily_quality">Daily AWS Quality</option>
              <option value="weekly_anomaly">Weekly Anomaly</option>
              <option value="station_health">Station Health</option>
              <option value="maintenance">Maintenance</option>
              <option value="regional_quality">Regional Data Quality</option>
            </select>
          </label>
          <label className="text-xs">Station (optional)
            <select value={stationId} onChange={(e) => setStationId(e.target.value)} className={`${inputCls} mt-1 w-full`}>
              <option value="">All stations</option>
              {(stations.data ?? []).map((s) => (
                <option key={s.station_id} value={s.station_id}>{s.station_id}</option>
              ))}
            </select>
          </label>
          <label className="text-xs">Window (days 1–90)
            <input type="number" min={1} max={90} value={days} onChange={(e) => setDays(Number(e.target.value))} className={`${inputCls} mt-1 w-full`} />
          </label>
        </div>
        <div className="mt-3">
          {preview ? <ReportView report={preview} /> : <EmptyState message="Choose a report and press Preview or Generate." />}
        </div>
      </Card>

      <Card title="Persisted runs" subtitle="Generate stores an immutable snapshot">
        {(runs.data ?? []).length === 0 ? (
          <EmptyState message="No stored runs yet." />
        ) : (
          <DataTable
            columns={[
              { header: 'ID', render: (r) => <span className="text-slate-500">#{r.id}</span> },
              { header: 'Type', render: (r) => <span className="text-xs">{r.report_type}</span> },
              { header: 'Created', render: (r) => <span className="whitespace-nowrap">{formatTs(r.created_at)}</span> },
              { header: 'Summary', render: (r) => <span className="text-xs">{r.summary}</span> },
              { header: '', render: (r) => <button className={btnGhost} onClick={() => openRun(r.id)}>Open</button> },
            ]}
            rows={runs.data ?? []}
            rowKey={(r) => r.id}
          />
        )}
      </Card>
    </div>
  );
}
