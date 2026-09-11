import { MonitorPlay, X } from 'lucide-react';
import { useClock } from '../hooks';
import { usePresentation } from '../presentation';

export default function PresentBar({ simRunning }: { simRunning: boolean }) {
  const now = useClock();
  const { exit } = usePresentation();
  return (
    <header className="sticky top-0 z-20 flex h-12 items-center gap-3 border-b border-slate-800 bg-slate-950/95 px-4 text-slate-100 backdrop-blur">
      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">S</span>
      <span className="text-sm font-bold tracking-widest">SKYGUARD AI · SIH DEMO</span>
      {simRunning && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-2.5 py-1 text-xs font-bold text-red-400">
          <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" /> LIVE
        </span>
      )}
      <span className="ml-auto text-sm tabular-nums text-slate-300">{now.toLocaleTimeString()}</span>
      <button
        onClick={exit}
        className="inline-flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700"
      >
        <X size={15} /> EXIT PRESENTATION MODE
      </button>
    </header>
  );
}

export function PresentEnterButton() {
  const { enter } = usePresentation();
  return (
    <button
      onClick={enter}
      title="Presentation mode for recording"
      className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
    >
      <MonitorPlay size={15} /> PRESENTATION MODE
    </button>
  );
}
