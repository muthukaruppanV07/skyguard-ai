import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePoll } from '../hooks';
import {
  anomaliesApi,
  explainApi,
  maintenanceApi,
  observationsApi,
  sensorHealthApi,
  simApi,
  spatialApi,
  stationsApi,
} from '../api/client';
import type { ExplanationResponse } from '../types';
import { Card, EmptyState, StatusBadge, btnGhost, btnPrimary } from '../components/ui';
import { usePresentation } from '../presentation';
import { PresentEnterButton } from '../components/PresentBar';
import StationMap from '../components/StationMap';

interface Chapter {
  id: string;
  title: string;
  time: string;
  dur: number;
  script: string;
}

const CHAPTERS: Chapter[] = [
  { id: 'intro', title: 'INTRO', time: '00:00–00:30', dur: 30, script: 'SKYGUARD AI — Trustworthy Weather Data. Smarter Stations. Safer Decisions.' },
  { id: 'network', title: 'LIVE AWS NETWORK', time: '00:30–01:15', dur: 45, script: 'India AWS map. Live station health from the backend.' },
  { id: 'anomaly', title: 'SENSOR ANOMALY', time: '01:15–02:00', dur: 45, script: 'Inject a 55°C spike on one station; neighbours stay near 31–32°C.' },
  { id: 'investigation', title: 'AI INVESTIGATION', time: '02:00–03:00', dur: 60, script: 'Detection pipeline, score, confidence, evidence, explainable AI, neighbours.' },
  { id: 'verdict', title: 'WEATHER vs SENSOR', time: '03:00–04:00', dur: 60, script: 'Isolated fault verdict — then a multi-station event verdict.' },
  { id: 'health', title: 'SENSOR HEALTH', time: '04:00–04:30', dur: 30, script: 'Health impact and a real maintenance recommendation.' },
  { id: 'summary', title: 'FINAL SUMMARY', time: '04:30–05:00', dur: 30, script: 'Detect. Explain. Protect.' },
];

interface DemoData {
  target?: string;
  targetTemp?: number;
  magnitude?: number;
  detection?: { type: string; score: number; temp: number };
  explanation?: ExplanationResponse | null;
  spatial?: { mean?: number; table: { id: string; temp: number | null; outlier: boolean }[] };
  verdict1?: string;
  verdict2?: string;
  health?: { overall: number; status: string };
  maintenance?: string;
  network?: { stations: number; healthy: number };
  ticks?: number;
}

const fmtT = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

export default function Demo() {
  const [phase, setPhase] = useState<'idle' | 'running' | 'paused' | 'done'>('idle');
  const [autoplay, setAutoplay] = useState(true);
  const [chapter, setChapter] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [data, setData] = useState<DemoData>({});
  const stations = usePoll(() => stationsApi.list(), 60000);
  const health = usePoll(() => sensorHealthApi.overview(), 15000);

  const demoStart = useRef<string>('');
  const elapsedTotal = useRef(0);
  const tickTotal = useRef(0);
  const pushLog = (line: string) => setLog((l) => [...l.slice(-60), `${fmtT(elapsedTotal.current)} ${line}`]);

  const merge = (patch: Partial<DemoData>) => setData((d) => ({ ...d, ...patch }));

  async function liveTick() {
    const res = await simApi.tick();
    tickTotal.current += 1;
    merge({ ticks: tickTotal.current });
    return res;
  }

  async function runChapterActions(idx: number) {
    const id = CHAPTERS[idx].id;
    try {
      if (id === 'network') {
        for (let i = 0; i < 3; i++) {
          await liveTick();
        }
        const [sts, h] = await Promise.all([stationsApi.list(), sensorHealthApi.overview()]);
        const healthy = h.filter((x) => ['EXCELLENT', 'GOOD'].includes(x.status)).length;
        merge({ network: { stations: sts.length, healthy } });
        pushLog(`Network live: ${healthy}/${sts.length} stations healthy (backend data).`);
      }
      if (id === 'anomaly') {
        const obs = await observationsApi.list({ limit: 400 });
        const latest = new Map<string, { temperature: number }>();
        for (const o of obs) latest.set(o.station_id, { temperature: o.temperature });
        let target = 'AWS002';
        let best = Infinity;
        for (const [sid, v] of latest) {
          const d = Math.abs(v.temperature - 31.5);
          if (d < best) {
            best = d;
            target = sid;
          }
        }
        const cur = latest.get(target)?.temperature ?? 32;
        const magnitude = Math.min(5, Math.max(0.1, (55 - cur) / 12));
        await simApi.inject({ scenario_id: 'temp_spike', station_ids: [target], duration_ticks: 4, magnitude });
        let found: DemoData['detection'];
        for (let i = 0; i < 5 && !found; i++) {
          const tick = await liveTick() as {
            readings: { station_id: string; temperature?: number }[];
            detections: { station_id: string; anomaly_type: string; anomaly_score: number }[];
          };
          const det = tick.detections.find((d) => d.station_id === target);
          const reading = tick.readings.find((r) => r.station_id === target);
          if (det && reading?.temperature !== undefined) {
            found = { type: det.anomaly_type, score: det.anomaly_score, temp: reading.temperature };
          }
        }
        merge({ target, targetTemp: cur, magnitude, detection: found });
        pushLog(found ? `ANOMALY DETECTED: ${target} ${found.type} score ${found.score.toFixed(0)} at ${found.temp.toFixed(1)}°C.` : `No detection on ${target} — see log.`);
      }
      if (id === 'investigation') {
        const target = data.target ?? 'AWS002';
        const list = await anomaliesApi.list({ station_id: target, limit: 5 });
        const fresh = list.find((a) => a.timestamp >= demoStart.current) ?? list[0];
        if (fresh) {
          const exp = await explainApi.get(fresh.id);
          merge({ explanation: exp });
          pushLog(`Investigation loaded: anomaly #${fresh.id}, score ${fresh.score.toFixed(0)}, confidence ${(fresh.confidence * 100).toFixed(0)}%.`);
        } else {
          pushLog('No anomaly row found for investigation.');
        }
        try {
          const sp = await spatialApi.station(target, { k: 4 });
          const mean = sp.neighbor_mean_c ?? undefined;
          const table = (sp.neighbors ?? []).map((n) => ({
            id: n.station_id,
            temp: n.temperature,
            outlier: n.temp_deviation !== null && Math.abs(n.temp_deviation) > 4,
          }));
          merge({ spatial: { mean, table } });
        } catch {
          pushLog('Spatial API unavailable for neighbor table.');
        }
      }
      if (id === 'verdict') {
        const v1 = data.explanation?.stored_classification as { event_type?: string } | null;
        merge({ verdict1: (v1?.event_type as string) ?? data.explanation?.stored?.event_type ?? undefined });
        await simApi.inject({ scenario_id: 'multi_station_event', duration_ticks: 3 });
        let withEvent;
        for (let i = 0; i < 5; i++) {
          const tk = (await liveTick()) as {
            detections: { station_id: string; anomaly_type: string; anomaly_score: number; event_type?: string }[];
          };
          withEvent = tk.detections.find((d) => d.event_type) ?? (tk.detections.length >= 2 ? tk.detections[0] : undefined);
          if (withEvent) break;
        }
        if (withEvent) {
          merge({ verdict2: withEvent.event_type ?? withEvent.anomaly_type });
          pushLog(`Second scenario verdict: ${withEvent.event_type ?? withEvent.anomaly_type} on ${withEvent.station_id}.`);
        } else {
          const recent = await anomaliesApi.list({ limit: 10 });
          const other = recent.find((a) => a.timestamp >= demoStart.current && a.station_id !== data.target);
          if (other) {
            const exp = await explainApi.get(other.id);
            const cls = exp.stored_classification as { event_type?: string } | null;
            merge({ verdict2: cls?.event_type ?? exp.stored?.event_type ?? other.root_cause });
            pushLog(`Second scenario verdict from stored row: ${other.root_cause} on ${other.station_id}.`);
          } else {
            pushLog('Second scenario produced no new verdict yet.');
          }
        }
      }
      if (id === 'health') {
        const target = data.target ?? 'AWS002';
        const h = await sensorHealthApi.detail(target);
        merge({ health: { overall: h.overall, status: h.status } });
        const m = await maintenanceApi.sync(target);
        const me = m.sensors.find((s) => s.sensor_type === 'TEMPERATURE') ?? m.sensors[0];
        merge({ maintenance: me ? `${me.maintenance_priority}: ${me.reason}` : 'No recommendation returned.' });
        pushLog(`Health ${h.overall.toFixed(0)}/100 (${h.status}); maintenance synced.`);
      }
    } catch (e: unknown) {
      pushLog(`Step failed: ${e instanceof Error ? e.message : 'backend error'} — continuing with live data.`);
    }
  }

  // Timer
  useEffect(() => {
    if (phase !== 'running' || !autoplay) return;
    const t = setInterval(() => {
      setElapsed((e) => {
        elapsedTotal.current += 1;
        const next = e + 1;
        if (next >= CHAPTERS[chapter].dur) {
          const nc = chapter + 1;
          if (nc >= CHAPTERS.length) {
            setPhase('done');
            return e;
          }
          setChapter(nc);
          void runChapterActions(nc);
          return 0;
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, autoplay, chapter]);

  const startDemo = async () => {
    setBusy(true);
    try {
      demoStart.current = new Date().toISOString();
      elapsedTotal.current = 0; tickTotal.current = 0;
      setLog([]);
      setData({});
      setChapter(0);
      setElapsed(0);
      await simApi.stop().catch(() => undefined);
      // Clear any stale scenario; keep the live clock so detection history stays valid.
      await simApi.inject({ scenario_id: 'normal' }).catch(() => undefined);
      setPhase('running');
      pushLog('Demo started: background loop stopped, history intact, manual ticks only.');
    } finally {
      setBusy(false);
    }
  };

  const nextEvent = async () => {
    if (phase === 'done') return;
    if (phase === 'idle') {
      await startDemo();
      return;
    }
    const nc = Math.min(chapter + 1, CHAPTERS.length - 1);
    setChapter(nc);
    setElapsed(0);
    await runChapterActions(nc);
    if (nc === CHAPTERS.length - 1 && !autoplay) {
      // manual mode stays on summary until RESET
    }
  };

  const resetDemo = async () => {
    await simApi.stop().catch(() => undefined);
    await simApi.reset().catch(() => undefined);
    setPhase('idle');
    setChapter(0);
    setElapsed(0);
    elapsedTotal.current = 0; tickTotal.current = 0;
    setData({});
    setLog([]);
  };

  const ch = CHAPTERS[chapter];
  const presenting = usePresentation().enabled;
  const { exit: exitPresentation } = usePresentation();

  // Recording flow: one chapter per viewport, no manual scrolling needed.
  useEffect(() => {
    if (presenting) window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [chapter, presenting]);
  const exp = data.explanation;
  const cls = exp?.stored_classification as {
    event_type?: string;
    sensor_fault_probability?: number;
    weather_event_probability?: number;
  } | null;
  const checklist: [string, boolean][] = [
    ['Real-time detection', !!data.detection],
    ['Temporal intelligence', !!(exp?.live?.methods_triggered?.some((m) => /temporal|drift|frozen|rate/.test(m.detector)))],
    ['Multivariate analysis', (cls?.sensor_fault_probability ?? 0) + (cls?.weather_event_probability ?? 0) > 0 || !!data.detection],
    ['Spatial intelligence', !!(data.spatial && data.spatial.table.length > 0)],
    ['Explainable AI', !!exp?.stored?.main_reason],
    ['Sensor health', data.health !== undefined],
    ['Predictive maintenance', !!data.maintenance],
    ['Scalable architecture', (data.network?.stations ?? 0) > 0],
    ['Live streaming', (data.ticks ?? 0) > 0],
  ];

  return (
    <div className={`page-enter mx-auto max-w-5xl space-y-4 p-4 ${presenting ? 'present-demo' : ''}`}>
      <Card
        title="5-Minute SIH Demo Mode"
        subtitle="Scripted story, real backend + ML pipeline — no canned animations"
        action={
          <div className="flex flex-wrap gap-2">
            <button disabled={busy || phase === 'running'} className={btnPrimary} onClick={startDemo}>START DEMO</button>
            <button disabled={phase !== 'running'} className={btnGhost} onClick={() => setPhase('paused')}>PAUSE</button>
            {phase === 'paused' && <button className={btnPrimary} onClick={() => setPhase('running')}>RESUME</button>}
            <button className={btnGhost} onClick={resetDemo}>RESET</button>
            <button disabled={busy || phase === 'done'} className={btnGhost} onClick={nextEvent}>NEXT EVENT →</button>
            <label className="flex items-center gap-1.5 text-xs text-slate-500">
              <input type="checkbox" checked={autoplay} onChange={(e) => setAutoplay(e.target.checked)} /> AUTO PLAY
            </label>
            {!presenting ? (
              <PresentEnterButton />
            ) : (
              <button className={btnGhost} onClick={exitPresentation}>EXIT PRESENTATION MODE</button>
            )}
          </div>
        }
      >
        <div className="mb-2 flex items-center gap-3 text-sm">
          <span className={`font-bold ${presenting ? 'text-xl' : ''}`}>{ch.title}</span>
          <span className="text-xs text-slate-500">{ch.time}</span>
          <span className="ml-auto font-mono tabular-nums">{fmtT(elapsedTotal.current)} / 05:00</span>
        </div>
        <span className="block h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
          <span className="block h-full bg-blue-600 transition-all" style={{ width: `${Math.min(100, (elapsedTotal.current / 300) * 100)}%` }} />
        </span>
        {!presenting && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {CHAPTERS.map((c, i) => (
              <button
                key={c.id}
                onClick={async () => {
                  setChapter(i);
                  setElapsed(0);
                  if (phase === 'running' || phase === 'paused') await runChapterActions(i);
                }}
                className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${i === chapter ? 'bg-blue-600 text-white' : i < chapter ? 'bg-emerald-500/20 text-emerald-500' : 'bg-slate-200 text-slate-500 dark:bg-slate-800'}`}
              >
                {c.title}
              </button>
            ))}
          </div>
        )}
        <p className={`mt-2 italic text-slate-500 ${presenting ? 'text-lg' : 'text-sm'}`}>{ch.script}</p>
      </Card>

      {chapter === 0 && (
        <div className={`rounded-2xl bg-gradient-to-r from-blue-700 to-indigo-800 text-center text-white shadow-card ${presenting ? 'p-14' : 'p-8'}`}>
          <h1 className={`font-extrabold tracking-wide ${presenting ? 'text-6xl' : 'text-3xl'}`}>SKYGUARD AI</h1>
          <p className={`mt-2 text-blue-100 ${presenting ? 'text-2xl' : ''}`}>Trustworthy Weather Data. Smarter Stations. Safer Decisions.</p>
        </div>
      )}

      {chapter >= 1 && (
        <Card title="Live AWS network" subtitle={data.network ? `${data.network.healthy}/${data.network.stations} stations healthy (live)` : 'Reading live health…'}>
          <StationMap
            stations={(stations.data ?? []).filter((s) => s.station_id !== 'SYSTEM')}
            healthByStation={Object.fromEntries((health.data ?? []).map((h) => [h.station_id, h.status]))}
            height={presenting ? 520 : 380}
          />
        </Card>
      )}

      {data.detection && (
        <Card title="Anomaly detected" subtitle={`${data.target} spiked toward 55°C while neighbours held 31–32°C`}>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <StatusBadge value={data.detection.score >= 85 ? 'CRITICAL' : 'HIGH'} pulse />
            <span className="font-bold">{data.detection.type}</span>
            <span className="tabular-nums">score {data.detection.score.toFixed(0)} · observed {data.detection.temp.toFixed(1)}°C</span>
          </div>
        </Card>
      )}

      {chapter >= 3 && exp && (
        <Card title="AI investigation" subtitle="Pipeline: ingest → features → detection → classification → explanation → alert">
          <p className="rounded-lg bg-blue-500/10 p-3 text-sm font-medium">{exp.stored?.main_reason ?? 'Explanation pending.'}</p>
          <div className="mt-2 grid grid-cols-2 gap-2 text-sm tabular-nums xl:grid-cols-4">
            <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60"><p className="text-[11px] uppercase text-slate-500">Score</p><p className="text-lg font-bold">{exp.live?.anomaly_score.toFixed(0) ?? '—'}</p></div>
            <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60"><p className="text-[11px] uppercase text-slate-500">Confidence</p><p className="text-lg font-bold">{exp.live ? `${(exp.live.confidence * 100).toFixed(0)}%` : '—'}</p></div>
            <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60"><p className="text-[11px] uppercase text-slate-500">Detectors fired</p><p className="text-lg font-bold">{exp.live?.methods_triggered.length ?? 0}</p></div>
            <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60"><p className="text-[11px] uppercase text-slate-500">Event</p><p className="text-sm font-bold">{exp.stored?.event_type ?? '—'}</p></div>
          </div>
          <p className="mt-2 text-sm font-semibold">{exp.stored?.conclusion}</p>
          {data.spatial && data.spatial.table.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-left text-sm tabular-nums">
                <thead><tr className="text-xs uppercase text-slate-500"><th className="px-2 py-1">Station</th><th className="px-2 py-1">Temp °C</th><th className="px-2 py-1">Note</th></tr></thead>
                <tbody>
                  <tr className="border-t border-slate-200 dark:border-slate-800">
                    <td className="px-2 py-1 font-bold">{data.target} ★</td>
                    <td className="px-2 py-1 font-bold text-red-500">{data.detection ? `${data.detection.temp.toFixed(1)} ⚠ OUTLIER` : '—'}</td>
                    <td className="px-2 py-1 text-xs">flagged station</td>
                  </tr>
                  {data.spatial.table.map((n) => (
                    <tr key={n.id} className="border-t border-slate-100 dark:border-slate-800/60">
                      <td className="px-2 py-1">{n.id}</td>
                      <td className="px-2 py-1">{n.temp !== null ? n.temp.toFixed(1) : '—'}</td>
                      <td className="px-2 py-1 text-xs text-slate-500">neighbour</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {chapter >= 4 && (data.verdict1 || data.verdict2) && (
        <Card title="Weather vs sensor" subtitle="Same classifier, two real scenarios">
          <div className="grid gap-2 xl:grid-cols-2">
            <div className="rounded-lg bg-red-500/10 p-3 text-sm"><p className="font-bold">Isolated spike → {data.verdict1 ?? '…'}</p></div>
            <div className="rounded-lg bg-emerald-500/10 p-3 text-sm"><p className="font-bold">Multi-station event → {data.verdict2 ?? 'running…'}</p></div>
          </div>
        </Card>
      )}

      {chapter >= 5 && data.health && (
        <Card title="Sensor health" subtitle="Live penalties + synced maintenance order">
          <p className="text-sm">Overall <b className="tabular-nums">{data.health.overall.toFixed(0)}/100</b> ({data.health.status})</p>
          {data.maintenance && <p className="mt-1 text-sm">{data.maintenance}</p>}
        </Card>
      )}

      {chapter >= 6 && (
        <div className={`rounded-2xl bg-gradient-to-r from-emerald-700 to-teal-800 text-white shadow-card ${presenting ? 'p-10' : 'p-6'}`}>
          <h2 className={`font-extrabold ${presenting ? 'text-3xl' : 'text-xl'}`}>Final summary</h2>
          <ul className={`mt-2 grid gap-1 xl:grid-cols-2 ${presenting ? 'text-lg' : 'text-sm'}`}>
            {[
              ['Real-time detection', 0], ['Temporal intelligence', 1], ['Multivariate analysis', 2],
              ['Spatial intelligence', 3], ['Explainable AI', 4], ['Sensor health', 5],
              ['Predictive maintenance', 6], ['Scalable architecture', 7], ['Live streaming', 8],
            ].map(([label, i]) => (
              <li key={label as string}>
                {checklist[i as number][1] ? '✓' : '○'} {label}
              </li>
            ))}
          </ul>
          <p className={`mt-3 font-bold tracking-wide ${presenting ? 'text-2xl' : 'text-lg'}`}>Detect. Explain. Protect.</p>
        </div>
      )}

      {!presenting && (
        <Card title="Demo log" subtitle="Every line records a real backend call result">
          {log.length === 0 ? <p className="text-sm text-slate-500">Press START DEMO. Each chapter runs live API calls; nothing is staged.</p> : (
            <ul className="max-h-56 space-y-1 overflow-y-auto font-mono text-xs">
              {log.map((l, i) => (
                <li key={i} className="border-b border-slate-100 py-0.5 dark:border-slate-800/60">{l}</li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
