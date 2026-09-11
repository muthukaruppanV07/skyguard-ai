import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { usePoll, formatTs } from '../hooks';
import { alertsApi, anomaliesApi, explainApi, observationsApi, stationsApi } from '../api/client';
import { Card, DataTable, EmptyState, ErrorState, Loading, Stat, StatusBadge, btnGhost, btnPrimary } from '../components/ui';

function haversineKm(a: number, b: number, c: number, d: number): number {
  const r = 6371;
  const p1 = (a * Math.PI) / 180;
  const p2 = (c * Math.PI) / 180;
  const dp = ((c - a) * Math.PI) / 180;
  const dl = ((d - b) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

function Section({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <Card title={`${n}. ${title}`}>
      {children}
    </Card>
  );
}

export default function AnomalyDetail() {
  const { anomalyId = '' } = useParams();
  const navigate = useNavigate();
  const id = Number(anomalyId);
  const explanation = usePoll(() => explainApi.get(id), null, [id]);
  const anomalies = usePoll(() => anomaliesApi.list({ limit: 500 }), 30000);
  const anomaly = (anomalies.data ?? []).find((a) => a.id === id);

  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [resolved, setResolved] = useState<boolean | null>(null);
  const [ackId, setAckId] = useState<number | null>(null);
  const [acked, setAcked] = useState<boolean | null>(null);

  const stationId = anomaly?.station_id;
  const obs = usePoll(
    () => observationsApi.list({ station_id: stationId ?? '', limit: 500 }),
    stationId ? 30000 : null,
    [stationId],
  );
  const allObs = usePoll(() => observationsApi.list({ limit: 500 }), 30000);
  const allStations = usePoll(() => stationsApi.list(), 60000);
  const stationAlerts = usePoll(
    () => alertsApi.list({ station_id: stationId ?? '', limit: 50 }),
    stationId ? 15000 : null,
    [stationId],
  );

  useEffect(() => {
    setResolved(anomaly?.resolved ?? null);
    const alert = (stationAlerts.data ?? []).find((a) => a.anomaly_id === id);
    setAckId(alert?.id ?? null);
    setAcked(alert?.acknowledged ?? null);
  }, [anomaly?.resolved, stationAlerts.data, id]);

  const doAcknowledge = async () => {
    if (ackId === null) return;
    setBusy('ack');
    try {
      const r = await alertsApi.acknowledge(ackId, true);
      setAcked(r.acknowledged);
      setNotice(`Alert #${ackId} acknowledged.`);
      stationAlerts.refresh();
    } catch (e: unknown) {
      setNotice(e instanceof Error ? e.message : 'Acknowledge failed');
    } finally {
      setBusy(null);
    }
  };

  const doResolve = async () => {
    setBusy('resolve');
    try {
      const r = await anomaliesApi.resolve(id);
      setResolved(r.resolved);
      setNotice(`Anomaly #${id} marked resolved.`);
      anomalies.refresh();
    } catch (e: unknown) {
      setNotice(e instanceof Error ? e.message : 'Resolve failed');
    } finally {
      setBusy(null);
    }
  };

  const { stored, stored_classification: cls, stored_guard: guard, live } = explanation.data ?? {};
  const view = live ?? null;

  const timeline = useMemo(() => {
    if (!anomaly || !obs.data) return [];
    const t0 = +new Date(anomaly.timestamp);
    return [...obs.data]
      .sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp))
      .filter((o) => Math.abs(+new Date(o.timestamp) - t0) <= 24 * 3600 * 1000)
      .slice(-25)
      .map((o) => ({
        t: new Date(o.timestamp).toLocaleString(),
        temp: o.temperature,
        isAnomaly: Math.abs(+new Date(o.timestamp) - t0) < 30 * 60 * 1000,
        anomalyTemp: Math.abs(+new Date(o.timestamp) - t0) < 30 * 60 * 1000 ? o.temperature : null,
      }));
  }, [anomaly, obs.data]);

  const observedVsExpected = useMemo(() => {
    const feats = view?.contributing_features ?? [];
    const linked = (obs.data ?? []).find(
      (o) => anomaly && Math.abs(+new Date(o.timestamp) - +new Date(anomaly.timestamp)) < 30 * 60 * 1000,
    );
    const rows: { param: string; observed: number | null; expected: number | null }[] = [];
    for (const s of ['temperature', 'pressure', 'humidity'] as const) {
      const f = feats.find((x) => x.sensor === s);
      const observed = linked ? linked[s] : null;
      rows.push({ param: s, observed, expected: f?.baseline ?? null });
    }
    return rows.filter((r) => r.observed !== null || r.expected !== null);
  }, [view, obs.data, anomaly]);

  const neighbors = useMemo(() => {
    if (!anomaly || !allStations.data || !allObs.data) return [];
    const me = allStations.data.find((s) => s.station_id === anomaly.station_id);
    if (!me) return [];
    const t0 = +new Date(anomaly.timestamp);
    const byStation = new Map<string, { ts: number; temperature: number; pressure: number; humidity: number }>();
    for (const o of allObs.data) {
      const dt = Math.abs(+new Date(o.timestamp) - t0);
      if (dt > 6 * 3600 * 1000) continue;
      const prev = byStation.get(o.station_id);
      if (!prev || dt < prev.ts) byStation.set(o.station_id, { ts: dt, temperature: o.temperature, pressure: o.pressure, humidity: o.humidity });
    }
    const temps = [...byStation.values()].map((v) => v.temperature);
    const m = temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : 0;
    const sd = temps.length > 1 ? Math.sqrt(temps.reduce((a, b) => a + (b - m) ** 2, 0) / temps.length) : 0;
    return allStations.data
      .filter((s) => s.station_id !== anomaly.station_id)
      .map((s) => ({ ...s, distance: haversineKm(me.latitude, me.longitude, s.latitude, s.longitude), reading: byStation.get(s.station_id) }))
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 4)
      .map((n) => ({
        ...n,
        z: n.reading ? (n.reading.temperature - m) / Math.max(sd, 0.5) : null,
      }));
  }, [anomaly, allStations.data, allObs.data]);

  if (explanation.error) return <div className="p-4"><ErrorState message={explanation.error} onRetry={explanation.refresh} /></div>;
  if (!explanation.data) return <div className="p-4"><Loading label="Reconstructing investigation…" /></div>;

  const pf = Number((cls as Record<string, number> | null)?.sensor_fault_probability ?? NaN);
  const pw = Number((cls as Record<string, number> | null)?.weather_event_probability ?? NaN);

  return (
    <div className="page-enter space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">Anomaly #{id} investigation</h1>
        {(resolved ?? anomaly?.resolved) && <StatusBadge value="LOW" />}
        {(resolved ?? anomaly?.resolved) ? <span className="text-xs font-bold text-emerald-500">RESOLVED</span> : null}
        {acked && <span className="text-xs font-bold text-blue-500">ACKNOWLEDGED</span>}
        <Link to="/anomalies" className="ml-auto text-sm text-blue-500 hover:underline">← Anomaly Center</Link>
      </div>

      {/* HEADER KPIs */}
      {anomaly && (
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <Stat label="Anomaly score" value={`${anomaly.score.toFixed(0)}/100`} accent={anomaly.score >= 85 ? '#ef4444' : '#f97316'} />
          <Stat label="Confidence" value={`${(anomaly.confidence * 100).toFixed(0)}%`} />
          <Stat label="Severity" value={<StatusBadge value={anomaly.severity} />} sub={formatTs(anomaly.timestamp)} />
          <Stat label="Root cause" value={<span className="text-base">{stored?.root_cause ?? anomaly.root_cause}</span>} sub={anomaly.station_id} />
        </div>
      )}

      {/* ACTION BUTTONS */}
      <Card title="Operator actions" subtitle={notice ?? 'Acknowledge the alert, resolve when handled, or review station history'}>
        <div className="flex flex-wrap gap-2">
          <button disabled={busy === 'ack' || ackId === null || acked === true} className={btnPrimary} onClick={doAcknowledge}>
            {acked ? 'Acknowledged ✓' : ackId === null ? 'No alert to acknowledge' : 'Acknowledge'}
          </button>
          <button disabled={busy === 'resolve' || resolved === true || anomaly?.resolved === true} className={btnGhost} onClick={doResolve}>
            {(resolved ?? anomaly?.resolved) ? 'Resolved ✓' : 'Resolve'}
          </button>
          <button className={btnGhost} onClick={() => anomaly && navigate(`/stations/${anomaly.station_id}/intel`)}>View History</button>
        </div>
      </Card>

      {/* WHY */}
      {stored ? (
        <Card title="WHY WAS THIS FLAGGED?" subtitle={`Root cause: ${stored.root_cause} · Event: ${stored.event_type ?? '—'}`}>
          <p className="rounded-lg bg-blue-500/10 p-3 text-sm font-medium leading-relaxed">{stored.main_reason}</p>
          <p className="mt-2 text-sm font-semibold">{stored.conclusion}</p>
        </Card>
      ) : (
        <EmptyState message="No stored explanation for this anomaly (legacy row)." />
      )}

      {/* 1. EVIDENCE TIMELINE */}
      <Section n="1" title="Evidence timeline">
        {timeline.length === 0 ? <EmptyState message="Not enough surrounding observations." /> : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={timeline}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="t" tick={false} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} width={40} />
              <Tooltip />
              <Line type="monotone" dataKey="temp" name="Temp °C" stroke="#3b82f6" dot={false} strokeWidth={2} />
              {timeline.map((p, i) =>
                p.isAnomaly ? <ReferenceDot key={i} x={p.t} y={p.anomalyTemp as number} r={6} fill="#ef4444" stroke="#fff" /> : null,
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
      </Section>

      {/* 2. OBSERVED vs EXPECTED */}
      <Section n="2" title="Observed vs expected">
        {observedVsExpected.length === 0 ? <EmptyState message="No baseline available." /> : (
          <DataTable
            columns={[
              { header: 'Parameter', render: (r) => <span className="font-medium">{r.param}</span> },
              { header: 'Observed', render: (r) => <span className="font-bold">{r.observed !== null ? r.observed.toFixed(1) : '—'}</span> },
              { header: 'Expected (rolling baseline)', render: (r) => <span>{r.expected !== null ? r.expected.toFixed(1) : '—'}</span> },
              {
                header: 'Δ',
                render: (r) =>
                  r.observed !== null && r.expected !== null ? (
                    <span className="font-bold" style={{ color: Math.abs(r.observed - r.expected) > 3 ? '#f97316' : undefined }}>
                      {(r.observed - r.expected >= 0 ? '+' : '') + (r.observed - r.expected).toFixed(1)}
                    </span>
                  ) : (
                    <span>—</span>
                  ),
              },
            ]}
            rows={observedVsExpected}
            rowKey={(r) => r.param}
          />
        )}
      </Section>

      {/* 3. CONTRIBUTING FACTORS */}
      <Section n="3" title="Contributing factors">
        {!stored?.top_contributors?.length ? <EmptyState message="No stored contributors." /> : (
          <ResponsiveContainer width="100%" height={Math.max(120, stored.top_contributors.length * 36)}>
            <BarChart data={stored.top_contributors.map((c) => ({ name: c.feature, share: c.contribution }))} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={180} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="share" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Section>

      {/* 4. FEATURE CONTRIBUTIONS */}
      <Section n="4" title="Feature contributions">
        {!view?.contributing_features?.length ? <EmptyState message="Live reconstruction unavailable for this row." /> : (
          <DataTable
            columns={[
              { header: 'Feature', render: (f) => <span className="text-xs">{f.feature}</span> },
              { header: 'Value', render: (f) => <span>{f.value !== null ? Number(f.value).toFixed(2) : '—'}</span> },
              { header: 'Baseline', render: (f) => <span>{f.baseline !== null ? Number(f.baseline).toFixed(2) : '—'}</span> },
              { header: 'z', render: (f) => <span className="font-bold">{f.z_score !== null ? Number(f.z_score).toFixed(1) : '—'}</span> },
              { header: 'Share %', render: (f) => <span className="font-bold">{f.contribution.toFixed(1)}</span> },
            ]}
            rows={view.contributing_features}
            rowKey={(f) => f.feature}
          />
        )}
      </Section>

      {/* 5. MULTIVARIATE */}
      <Section n="5" title="Multivariate consistency">
        {!cls ? <EmptyState message="No classification stored." /> : (
          <div className="grid grid-cols-3 gap-2 text-sm tabular-nums">
            {['spatial_consistency', 'temporal_consistency', 'multivariate_consistency'].map((k) => (
              <div key={k} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                <p className="text-[11px] uppercase text-slate-500">{k.replace('_consistency', '')}</p>
                <p className="text-lg font-bold">{Number((cls as Record<string, number>)[k] ?? 0).toFixed(2)}</p>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* 6+7. SPATIAL + NEIGHBORS */}
      <Section n="6/7" title="Spatial consistency & neighbor comparison">
        {neighbors.length === 0 ? <EmptyState message="No neighboring readings near anomaly time." /> : (
          <DataTable
            columns={[
              { header: 'Station', render: (n) => <span className="font-semibold">{n.station_id}</span> },
              { header: 'Dist km', render: (n) => n.distance.toFixed(0) },
              { header: 'Temp °C', render: (n) => <span className="font-bold">{n.reading ? n.reading.temperature.toFixed(1) : '—'}</span> },
              {
                header: 'z vs group',
                render: (n) =>
                  n.z !== null ? (
                    <span className="font-bold" style={{ color: Math.abs(n.z) > 2 ? '#ef4444' : undefined }}>
                      {n.z >= 0 ? '+' : ''}{n.z.toFixed(1)}{Math.abs(n.z) > 2 ? ' ⚠' : ''}
                    </span>
                  ) : (
                    <span>—</span>
                  ),
              },
            ]}
            rows={neighbors}
            rowKey={(n) => n.station_id}
          />
        )}
        {anomaly && (
          <p className="mt-2 text-sm">
            Flagged station <b>{anomaly.station_id}</b> — compare its reading against the neighbor group above; |z| &gt; 2 marks an outlier.
          </p>
        )}
      </Section>

      {/* 8. ROOT CAUSE EVIDENCE */}
      <Section n="8" title="Root cause evidence">
        {!view?.methods_triggered?.length ? <EmptyState message="No live detector trail for this row." /> : (
          <ul className="space-y-1 text-sm tabular-nums">
            {view.methods_triggered.map((m) => (
              <li key={m.detector} className="flex justify-between border-b border-slate-100 py-1 dark:border-slate-800/60">
                <span>{m.detector}</span>
                <span className="font-semibold">score {m.score.toFixed(1)} → +{m.contribution.toFixed(1)}</span>
              </li>
            ))}
          </ul>
        )}
        {(guard as unknown as { failed?: string[] } | null)?.failed !== undefined &&
          (guard as unknown as { failed: string[] }).failed.length > 0 && (
            <p className="mt-2 text-sm">False-alarm guard failed checks: {(guard as unknown as { failed: string[] }).failed.join(', ')}</p>
          )}
      </Section>

      {/* 9. WEATHER vs FAULT */}
      <Section n="9" title="Weather vs sensor fault">
        {Number.isNaN(pf) || Number.isNaN(pw) ? <EmptyState message="No stored probabilities." /> : (
          <div className="space-y-2 text-sm tabular-nums">
            {[['Sensor fault', pf, '#ef4444'], ['Weather event', pw, '#22c55e']].map(([label, v, color]) => (
              <div key={label as string} className="flex items-center gap-2">
                <span className="w-28">{label}</span>
                <span className="flex-1">
                  <span className="block h-3 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                    <span className="block h-full rounded-full" style={{ width: `${(v as number) * 100}%`, backgroundColor: color as string }} />
                  </span>
                </span>
                <span className="w-12 text-right font-bold">{((v as number) * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* 10. ACTION */}
      <Section n="10" title="Recommended action">
        <p className="text-sm leading-relaxed">{stored?.recommended_action ?? 'Review station maintenance log.'}</p>
        {stored && <p className="mt-2 text-sm font-semibold">{stored.conclusion}</p>}
      </Section>
    </div>
  );
}
