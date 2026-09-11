import { useEffect, useRef, useState } from 'react';
import { wsUrl, simApi } from '../api/client';
import type { TickMessage } from '../types';
import { Card, EmptyState, StatusBadge, btnGhost, btnPrimary } from '../components/ui';

export default function LiveMonitor({ onSimChange }: { onSimChange: (running: boolean) => void }) {
  const [connected, setConnected] = useState(false);
  const [ticks, setTicks] = useState<TickMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'tick') {
          setTicks((t) => [msg as TickMessage, ...t].slice(0, 20));
          onSimChange(msg.status === 'RUNNING');
        }
      } catch {
        /* ignore malformed */
      }
    };
    ws.onerror = () => setError('WebSocket error — is the backend running on :8001?');
    ws.onclose = () => setConnected(false);
    return () => {
      ws.close();
      onSimChange(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = (cmd: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(cmd));
  };

  const control = async (fn: () => Promise<unknown>, cmd?: object) => {
    setBusy(true);
    try {
      if (cmd) send(cmd);
      else await fn();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Control failed');
    } finally {
      setBusy(false);
    }
  };

  const latest = ticks[0];

  return (
    <div className="page-enter space-y-4 p-4">
      <Card
        title="Live stream"
        subtitle={connected ? 'WebSocket connected — ticks arrive in real time' : 'Connecting…'}
        action={
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${connected ? 'bg-emerald-500/15 text-emerald-500' : 'bg-red-500/15 text-red-500'}`}>
            <span className={`h-2 w-2 rounded-full ${connected ? 'animate-pulse bg-emerald-500' : 'bg-red-500'}`} />
            {connected ? 'CONNECTED' : 'OFFLINE'}
          </span>
        }
      >
        {error && <p className="mb-2 text-sm text-red-500">{error}</p>}
        <div className="flex flex-wrap gap-2">
          <button disabled={busy} className={btnPrimary} onClick={() => control(() => simApi.start(), { cmd: 'start' })}>Start</button>
          <button disabled={busy} className={btnGhost} onClick={() => control(() => simApi.pause(), { cmd: 'pause' })}>Pause</button>
          <button disabled={busy} className={btnGhost} onClick={() => control(() => simApi.resume(), { cmd: 'resume' })}>Resume</button>
          <button disabled={busy} className={btnGhost} onClick={() => control(() => simApi.stop(), { cmd: 'stop' })}>Stop</button>
          <button disabled={busy} className={btnGhost} onClick={() => control(() => simApi.reset(), { cmd: 'reset' })}>Reset</button>
          <button disabled={busy} className={btnGhost} onClick={() => control(() => simApi.tick())}>Single tick</button>
        </div>
      </Card>

      {latest ? (
        <Card title={`Tick #${latest.tick}`} subtitle={`Scenario: ${latest.scenario ?? 'normal'} · Detections: ${latest.detections.length}`}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm tabular-nums">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800">
                  <th className="px-2 py-2">Station</th>
                  <th className="px-2 py-2">Temp °C</th>
                  <th className="px-2 py-2">Press hPa</th>
                  <th className="px-2 py-2">Hum %</th>
                  <th className="px-2 py-2">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {latest.readings.map((r) => (
                  <tr key={r.station_id} className="border-b border-slate-100 dark:border-slate-800/60">
                    <td className="px-2 py-1.5 font-semibold">{r.station_id}</td>
                    {r.skipped ? (
                      <td colSpan={3} className="px-2 py-1.5 text-xs text-amber-500">GAP — no emission (streak {r.skip_streak})</td>
                    ) : (
                      <>
                        <td className="px-2 py-1.5">{r.temperature?.toFixed(1)}</td>
                        <td className="px-2 py-1.5">{r.pressure?.toFixed(1)}</td>
                        <td className="px-2 py-1.5">{r.humidity?.toFixed(1)}</td>
                      </>
                    )}
                    <td className="px-2 py-1.5">
                      {r.anomaly_type && r.anomaly_type !== 'NORMAL' ? (
                        <span className="flex items-center gap-2">
                          <StatusBadge value={r.anomaly_score && r.anomaly_score >= 70 ? 'HIGH' : 'SUSPICIOUS'} />
                          <span className="text-xs">{r.anomaly_type} · {r.event_type}</span>
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500">nominal</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <EmptyState message={connected ? 'Press Start (or Single tick) to stream observations through the real detection pipeline.' : 'Waiting for WebSocket connection…'} />
      )}

      {ticks.length > 1 && (
        <Card title="Tick history" subtitle="Most recent first">
          <ul className="space-y-1 text-sm tabular-nums">
            {ticks.slice(1, 11).map((t) => (
              <li key={t.tick} className="flex gap-3 border-b border-slate-100 py-1 dark:border-slate-800/60">
                <span className="font-semibold">#{t.tick}</span>
                <span className="text-slate-500">{t.readings.length} readings</span>
                <span className={t.detections.length ? 'font-semibold text-amber-500' : 'text-slate-500'}>
                  {t.detections.length} detections
                </span>
                <span className="text-xs text-slate-500">{t.scenario ?? 'normal'}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
