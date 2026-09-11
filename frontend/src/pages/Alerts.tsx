import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePoll, formatTs } from '../hooks';
import { alertsApi, anomaliesApi, stationsApi, wsUrl } from '../api/client';
import type { Alert, TickMessage } from '../types';
import { Card, EmptyState, ErrorState, Loading, StatusBadge, btnGhost, inputCls } from '../components/ui';

type Category = 'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO' | 'SYSTEM';

// Backend severities mapped onto operator categories (SUSPICIOUS watches as MEDIUM).
function categoryOf(severity: string): Exclude<Category, 'ALL'> {
  switch ((severity || '').toUpperCase()) {
    case 'CRITICAL': return 'CRITICAL';
    case 'HIGH': return 'HIGH';
    case 'SUSPICIOUS': return 'MEDIUM';
    case 'LOW': return 'LOW';
    case 'INFO':
    case 'NORMAL': return 'INFO';
    case 'SYSTEM': return 'SYSTEM';
    default: return 'LOW';
  }
}

const CATEGORIES: Category[] = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO', 'SYSTEM'];

interface LiveItem {
  key: string;
  station_id: string;
  severity: string;
  message: string;
  time: string;
  anomaly_score?: number;
  anomaly_id?: number;
}

export default function Alerts() {
  const navigate = useNavigate();
  const [category, setCategory] = useState<Category>('ALL');
  const [station, setStation] = useState('');
  const [showMuted, setShowMuted] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [live, setLive] = useState<LiveItem[]>([]);
  const [wsUp, setWsUp] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const alerts = usePoll(() => alertsApi.list({ limit: 200 }), 5000);
  const anomalies = usePoll(() => anomaliesApi.list({ limit: 200 }), 15000);
  const stations = usePoll(() => stationsApi.list(), 60000);

  useEffect(() => {
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;
    ws.onopen = () => setWsUp(true);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'tick') {
          const t = msg as TickMessage;
          const items: LiveItem[] = t.detections.map((d) => ({
            key: `live-${t.tick}-${d.station_id}`,
            station_id: d.station_id,
            severity: (d.anomaly_score ?? 0) >= 85 ? 'CRITICAL' : (d.anomaly_score ?? 0) >= 70 ? 'HIGH' : 'SUSPICIOUS',
            message: `${d.station_id}: ${d.anomaly_type} score=${d.anomaly_score} [${d.event_type}] (alert #${d.alert_id})`,
            time: new Date().toISOString(),
            anomaly_score: d.anomaly_score,
          }));
          if (items.length) setLive((prev) => [...items, ...prev].slice(0, 30));
        }
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => setWsUp(false);
    return () => ws.close();
  }, []);

  const anomalyById = useMemo(() => {
    const m = new Map<number, { score: number; confidence: number; root_cause: string; station_id: string }>();
    for (const a of anomalies.data ?? []) {
      m.set(a.id, { score: a.score, confidence: a.confidence, root_cause: a.root_cause, station_id: a.station_id });
    }
    return m;
  }, [anomalies.data]);

  const act = async (id: number, fn: () => Promise<unknown>) => {
    setBusy(id);
    try {
      await fn();
      alerts.refresh();
    } finally {
      setBusy(null);
    }
  };

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const a of alerts.data ?? []) {
      if (a.muted) continue;
      const cat = categoryOf(a.severity);
      c[cat] = (c[cat] ?? 0) + 1;
    }
    return c;
  }, [alerts.data]);

  const rows = useMemo(() => {
    return (alerts.data ?? []).filter(
      (a) =>
        (category === 'ALL' || categoryOf(a.severity) === category) &&
        (!station || a.station_id === station) &&
        (showMuted || !a.muted),
    );
  }, [alerts.data, category, station, showMuted]);

  if (alerts.error) {
    return (
      <div className="page-enter p-4">
        <ErrorState message={alerts.error} onRetry={alerts.refresh} />
      </div>
    );
  }

  const liveUnmuted = live; // stream items are never muted

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Alert Center"
        subtitle={`${alerts.data?.length ?? 0} backend alerts · live stream ${wsUp ? 'connected' : 'reconnecting…'} · SUSPICIOUS watches group under MEDIUM`}
        action={
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${wsUp ? 'bg-emerald-500/15 text-emerald-500' : 'bg-red-500/15 text-red-500'}`}>
            <span className={`h-2 w-2 rounded-full ${wsUp ? 'animate-pulse bg-emerald-500' : 'bg-red-500'}`} />
            {wsUp ? 'REALTIME' : 'POLLING'}
          </span>
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`rounded-full px-3 py-1 text-xs font-bold ${
                category === c
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
              }`}
            >
              {c}{c !== 'ALL' ? ` (${counts[c] ?? 0})` : ''}
            </button>
          ))}
          <select value={station} onChange={(e) => setStation(e.target.value)} className={`${inputCls} ml-auto`}>
            <option value="">All stations</option>
            {(stations.data ?? []).map((s) => (
              <option key={s.station_id} value={s.station_id}>{s.station_id}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-xs text-slate-500">
            <input type="checkbox" checked={showMuted} onChange={(e) => setShowMuted(e.target.checked)} />
            show muted
          </label>
        </div>

        {!alerts.data ? (
          <Loading />
        ) : (
          <div className="space-y-3">
            {liveUnmuted.length > 0 && (
              <div>
                <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-emerald-500">Just streamed in</p>
                {liveUnmuted.slice(0, 5).map((l) => (
                  <article key={l.key} className="mb-2 flex gap-3 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3">
                    <StatusBadge value={l.severity} pulse />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold">{l.station_id} <span className="ml-1 rounded bg-emerald-500 px-1.5 py-0.5 text-[10px] font-bold text-white">LIVE</span></p>
                      <p className="truncate text-sm">{l.message}</p>
                    </div>
                  </article>
                ))}
              </div>
            )}
            {rows.length === 0 && <EmptyState message="No alerts in this view — network quiet." />}
            {rows.map((a: Alert) => {
              const linked = a.anomaly_id != null ? anomalyById.get(a.anomaly_id) : undefined;
              return (
                <article
                  key={a.id}
                  className={`flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-start ${
                    a.muted ? 'border-slate-200 opacity-55 dark:border-slate-800' : 'border-slate-200 dark:border-slate-700'
                  } ${categoryOf(a.severity) === 'CRITICAL' ? 'border-l-4 border-l-red-500' : ''}`}
                >
                  <div className="sm:w-28 sm:shrink-0">
                    <StatusBadge value={a.severity} pulse={categoryOf(a.severity) === 'CRITICAL' && !a.acknowledged} />
                    {a.muted && <p className="mt-1 text-[11px] font-bold text-slate-400">MUTED</p>}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold">
                      {a.station_id}
                      {a.station_id === 'SYSTEM' && <span className="ml-1 text-xs font-normal text-slate-500">(command center)</span>}
                    </p>
                    <p className="break-words text-sm">{a.message}</p>
                    {linked && (
                      <p className="mt-1 text-xs tabular-nums text-slate-500">
                        Score {linked.score.toFixed(0)}/100 · Confidence {(linked.confidence * 100).toFixed(0)}% · Probable cause: {linked.root_cause}
                      </p>
                    )}
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      {formatTs(a.created_at)}
                      {a.acknowledged && <span className="ml-2 font-bold text-blue-500">ACKNOWLEDGED</span>}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-row flex-wrap gap-1.5 sm:max-w-44 sm:justify-end">
                    <button
                      className={btnGhost}
                      disabled={a.anomaly_id == null}
                      title={a.anomaly_id == null ? 'No linked anomaly' : 'Open investigation'}
                      onClick={() => a.anomaly_id != null && navigate(`/anomalies/${a.anomaly_id}`)}
                    >
                      Investigate
                    </button>
                    <button
                      className={btnGhost}
                      disabled={busy === a.id || a.acknowledged}
                      onClick={() => act(a.id, () => alertsApi.acknowledge(a.id, true))}
                    >
                      {a.acknowledged ? 'Acked ✓' : 'Acknowledge'}
                    </button>
                    <button
                      className={btnGhost}
                      disabled={busy === a.id}
                      onClick={() => act(a.id, () => alertsApi.mute(a.id, !a.muted))}
                    >
                      {a.muted ? 'Unmute' : 'Mute'}
                    </button>
                    <button
                      className={btnGhost}
                      disabled={busy === a.id || a.anomaly_id == null}
                      title={a.anomaly_id == null ? 'No linked anomaly' : 'Resolve linked anomaly (logs INFO alert)'}
                      onClick={() => a.anomaly_id != null && act(a.id, () => anomaliesApi.resolve(a.anomaly_id as number))}
                    >
                      Resolve
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
