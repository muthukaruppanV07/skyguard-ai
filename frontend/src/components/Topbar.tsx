import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, Menu, Moon, Search, Sun } from 'lucide-react';
import { useTheme } from '../theme';
import { PresentEnterButton } from './PresentBar';
import { useClock, usePoll } from '../hooks';
import { alertsApi, healthApi, stationsApi } from '../api/client';

export default function Topbar({ onMenu, simRunning }: { onMenu: () => void; simRunning: boolean }) {
  const { theme, toggle } = useTheme();
  const now = useClock();
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [showAlerts, setShowAlerts] = useState(false);
  const alerts = usePoll(() => alertsApi.list({ limit: 8 }), 15000);
  const backend = usePoll(() => healthApi.service(), 30000);
  const stations = usePoll(() => stationsApi.list(), 60000);
  const unacked = (alerts.data ?? []).filter((a) => !a.acknowledged).length;
  const backendOk = backend.data?.status === 'healthy';

  const matches = q.trim()
    ? (stations.data ?? []).filter(
        (s) => s.station_id.toLowerCase().includes(q.toLowerCase()) || s.name.toLowerCase().includes(q.toLowerCase()),
      ).slice(0, 6)
    : [];

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-slate-200 bg-white/90 px-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90 sm:gap-3 sm:px-4">
      <button onClick={onMenu} className="rounded-md p-2 hover:bg-slate-100 lg:hidden dark:hover:bg-slate-800" aria-label="Menu">
        <Menu size={18} />
      </button>
      <span
        className={`hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold sm:inline-flex ${
          simRunning ? 'bg-red-500/15 text-red-500' : 'bg-emerald-500/15 text-emerald-500'
        }`}
      >
        <span className={`h-2 w-2 rounded-full ${simRunning ? 'animate-pulse bg-red-500' : 'bg-emerald-500'}`} />
        {simRunning ? 'SIM LIVE' : 'LIVE'}
      </span>
      <div className="relative hidden flex-1 justify-center md:flex">
        <div className="relative w-full max-w-md">
          <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search stations…"
            className="w-full rounded-lg border border-slate-300 bg-slate-50 py-1.5 pl-8 pr-3 text-sm dark:border-slate-700 dark:bg-slate-800"
          />
          {matches.length > 0 && (
            <div className="absolute top-full z-30 mt-1 w-full rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900">
              {matches.map((s) => (
                <button
                  key={s.station_id}
                  onClick={() => {
                    setQ('');
                    navigate(`/stations/${s.station_id}`);
                  }}
                  className="block w-full px-3 py-1.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <span className="font-semibold">{s.station_id}</span> · {s.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="ml-auto flex items-center gap-1 sm:gap-2">
        <span className="hidden text-xs tabular-nums text-slate-500 lg:inline dark:text-slate-400">
          {now.toLocaleString()}
        </span>
        <span
          title={backendOk ? `Backend ${backend.data?.version}` : 'Backend unreachable'}
          className={`hidden rounded-full px-2 py-1 text-[11px] font-semibold sm:inline ${
            backendOk ? 'bg-emerald-500/15 text-emerald-500' : 'bg-red-500/15 text-red-500'
          }`}
        >
          SYS {backendOk ? 'OK' : 'DOWN'}
        </span>
        <div className="relative">
          <button
            onClick={() => setShowAlerts((v) => !v)}
            className="relative rounded-md p-2 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Notifications"
          >
            <Bell size={18} />
            {unacked > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {unacked}
              </span>
            )}
          </button>
          {showAlerts && (
            <div className="absolute right-0 top-full z-30 mt-1 w-80 rounded-lg border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
              <p className="px-2 py-1 text-xs font-semibold uppercase tracking-wider text-slate-500">Latest alerts</p>
              {(alerts.data ?? []).slice(0, 6).map((a) => (
                <Link
                  key={a.id}
                  to="/anomalies"
                  onClick={() => setShowAlerts(false)}
                  className="block rounded-md px-2 py-1.5 text-xs hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <span className="font-semibold">{a.severity}</span> · {a.message}
                </Link>
              ))}
              {(alerts.data ?? []).length === 0 && <p className="px-2 py-2 text-xs text-slate-500">No alerts.</p>}
            </div>
          )}
        </div>
        <button onClick={toggle} className="rounded-md p-2 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Theme">
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <span className="hidden xl:inline">
          <PresentEnterButton />
        </span>
      </div>
    </header>
  );
}
