import { NavLink } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  Bell,
  Clapperboard,
  Database,
  FileText,
  FlaskConical,
  HeartPulse,
  LayoutDashboard,
  Map as MapIcon,
  Network,
  Radio,
  Settings as SettingsIcon,
  ShieldAlert,
  Sparkles,
  Gavel,
  Trophy,
  Wrench,
} from 'lucide-react';

const ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/live', label: 'Live Monitor', icon: Radio },
  { to: '/stations', label: 'Stations', icon: MapIcon },
  { to: '/spatial', label: 'Spatial Intel', icon: Network },
  { to: '/anomalies', label: 'Anomaly Center', icon: ShieldAlert },
  { to: '/alerts', label: 'Alert Center', icon: Bell },
  { to: '/insights', label: 'AI Insights', icon: Sparkles },
  { to: '/health', label: 'Sensor Health', icon: HeartPulse },
  { to: '/maintenance', label: 'Predictive Maintenance', icon: Wrench },
  { to: '/data', label: 'Data Quality', icon: Database },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/simulation', label: 'Simulation', icon: Activity },
  { to: '/demo', label: 'SIH Demo', icon: Clapperboard },
  { to: '/evaluation', label: 'Evaluation', icon: FlaskConical },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/why', label: 'Why SkyGuard?', icon: Trophy },
  { to: '/judge', label: 'Judge Mode', icon: Gavel },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
];

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={onClose} />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-slate-200 bg-white transition-transform dark:border-slate-800 dark:bg-slate-950 ${
          open ? 'translate-x-0' : '-translate-x-full'
        } lg:translate-x-0`}
      >
        <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-4 dark:border-slate-800">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 font-bold text-white">S</span>
          <div>
            <p className="text-sm font-bold tracking-wide">SKYGUARD AI</p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">IMD · AWS Command</p>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto p-2">
          {ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onClose}
              className={({ isActive }) =>
                `mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600/10 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800/70'
                }`
              }
            >
              <item.icon size={17} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <p className="border-t border-slate-200 px-4 py-3 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-500">
          SIH 26073 · MoES / IMD
        </p>
      </aside>
    </>
  );
}
