import type { ReactNode } from 'react';

export const SEVERITY_COLORS: Record<string, string> = {
  NORMAL: '#22c55e',
  LOW: '#84cc16',
  SUSPICIOUS: '#facc15',
  HIGH: '#f97316',
  CRITICAL: '#ef4444',
  EXCELLENT: '#22c55e',
  GOOD: '#84cc16',
  WARNING: '#facc15',
  URGENT: '#ef4444',
  MEDIUM: '#facc15',
};

export function StatusBadge({ value, pulse }: { value: string; pulse?: boolean }) {
  const color = SEVERITY_COLORS[value?.toUpperCase()] ?? '#64748b';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${pulse ? 'animate-pulse' : ''}`}
      style={{ backgroundColor: `${color}22`, color, border: `1px solid ${color}55` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {value}
    </span>
  );
}

export function Card({ title, subtitle, action, children, className = '' }: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900 ${className}`}>
      {(title || action) && (
        <header className="mb-3 flex items-start justify-between gap-2">
          <div>
            {title && <h2 className="text-sm font-semibold tracking-wide text-slate-800 dark:text-slate-100">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums" style={accent ? { color: accent } : undefined}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{sub}</p>}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
      {message}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
      <p>Backend unreachable: {message}</p>
      <button onClick={onRetry} className="mt-2 rounded-md bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-500">
        Retry
      </button>
    </div>
  );
}

export function Loading({ label = 'Loading live data…' }: { label?: string }) {
  return <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">{label}</p>;
}

export function DataTable<T>({ columns, rows, rowKey, onRowClick }: {
  columns: { header: string; render: (row: T) => ReactNode; className?: string }[];
  rows: T[];
  rowKey: (row: T) => string | number;
  onRowClick?: (row: T) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:text-slate-400">
            {columns.map((c) => (
              <th key={c.header} className={`px-2 py-2 font-medium ${c.className ?? ''}`}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`border-b border-slate-100 tabular-nums dark:border-slate-800/60 ${
                onRowClick ? 'cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/60' : ''
              }`}
            >
              {columns.map((c) => (
                <td key={c.header} className={`px-2 py-2 ${c.className ?? ''}`}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const btnPrimary =
  'rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50';
export const btnGhost =
  'rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800 disabled:opacity-50';
export const inputCls =
  'rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100';
