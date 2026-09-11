import { Link } from 'react-router-dom';
import { usePoll } from '../hooks';
import { evalApi } from '../api/client';
import { Card, Loading, Stat, btnPrimary } from '../components/ui';

const ROWS: [string, string, string][] = [
  ['Detection', 'Fixed thresholds: in-range or out-of-range, nothing in between', 'Hybrid AI: 9 fused detectors vote on every reading (0–100 score)'],
  ['Time awareness', 'Limited temporal understanding: single-point checks', 'Temporal intelligence: rate-of-change, frozen runs, drift slopes, gap streaks'],
  ['Cross-sensor logic', 'Limited multivariate analysis: each channel alone', 'Multivariate analysis: T–H–P coupling breaks flagged with pattern alignment'],
  ['Geography', 'Limited spatial analysis: stations judged in isolation', 'Spatial intelligence: neighbour agreement, deviation, regional consistency'],
  ['Workflow', 'Manual investigation of every flag', 'Real-time monitoring: WebSocket stream, alert center, one-click acknowledge/mute/resolve'],
  ['Trust', 'Limited explanation: a bare out-of-range message', 'Explainable AI: why-flagged narrative, evidence, feature contributions, guard verdict'],
  ['Certainty', 'No confidence measure', 'Confidence scoring on every anomaly + weather-vs-fault probabilities'],
  ['Fleet care', 'No sensor tracking', 'Sensor health 0–100 with penalty breakdown + predictive maintenance work orders'],
  ['Recovery', 'Raw values only', 'Optional data correction: expected-value estimates stored beside raw data'],
];

export default function WhySkyguard() {
  const latest = usePoll(() => evalApi.latest().catch(() => null), null, []);
  const m = latest.data?.methods;

  return (
    <div className="page-enter mx-auto max-w-5xl space-y-4 p-4">
      <div className="rounded-2xl bg-gradient-to-r from-blue-700 to-indigo-800 p-6 text-white shadow-card">
        <p className="text-xs font-bold uppercase tracking-widest text-blue-200">SIH 26073 · MoES / IMD</p>
        <h1 className="mt-1 text-2xl font-extrabold sm:text-3xl">Why SkyGuard AI?</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-blue-100 sm:text-base">
          An unusual measurement is <b>not</b> automatically a sensor failure. SkyGuard proves, per reading,
          whether it is a fault or real weather — and shows its work.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to="/live" className={btnPrimary}>Watch it live</Link>
          <Link to="/evaluation" className="rounded-md border border-white/40 px-3 py-1.5 text-sm font-semibold text-white hover:bg-white/10">
            See the measured proof
          </Link>
        </div>
      </div>

      <Card title="The 30-second verdict" subtitle="Measured on labeled fault-injection episodes — not slides">
        {!latest.data ? (
          <p className="text-sm text-slate-500">
            {latest.loading ? <Loading label="Checking for measured runs…" /> : 'No evaluation run stored yet — '}
            {!latest.loading && !latest.data && (
              <Link to="/evaluation" className="font-semibold text-blue-500 hover:underline">run one now, numbers appear here automatically.</Link>
            )}
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Stat label="Hybrid F1" value={m!.hybrid.f1.toFixed(3)} sub={`threshold ${m!.threshold.f1.toFixed(3)}`} accent="#22c55e" />
            <Stat label="Hybrid precision" value={m!.hybrid.precision.toFixed(3)} sub={`threshold ${m!.threshold.precision.toFixed(3)}`} />
            <Stat label="Hybrid FPR" value={m!.hybrid.fpr.toFixed(3)} sub={`threshold ${m!.threshold.fpr.toFixed(3)} — lower is better`} accent="#22c55e" />
            <Stat label="Episodes" value={latest.data.episodes} sub={`seed ${latest.data.config.seed} · run from Evaluation page`} />
          </div>
        )}
      </Card>

      <Card title="Traditional QC vs SkyGuard AI" subtitle="Each SkyGuard claim links to a live page">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 dark:border-slate-800">
                <th className="px-2 py-2">Capability</th>
                <th className="px-2 py-2">Traditional QC</th>
                <th className="px-2 py-2">SkyGuard AI</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map(([cap, trad, sky]) => (
                <tr key={cap} className="border-b border-slate-100 align-top dark:border-slate-800/60">
                  <td className="px-2 py-2 font-bold">{cap}</td>
                  <td className="px-2 py-2 text-slate-500">✕ {trad}</td>
                  <td className="px-2 py-2"><span className="font-bold text-emerald-500">✓ </span>{sky}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        {[
          ['1 · Inject a fault', 'Simulation page fires spikes, freezes, drift, gaps and regional events into the live stream.'],
          ['2 · Watch the verdict', 'Live Monitor + Alert Center show score, fault-vs-weather probabilities and guard decision in real time.'],
          ['3 · Ask why', 'Every anomaly carries a generated explanation: evidence, contributors, neighbours, action.'],
        ].map(([t, d]) => (
          <Card key={t} title={t}>
            <p className="text-sm text-slate-600 dark:text-slate-300">{d}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
