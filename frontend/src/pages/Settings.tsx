import { useState } from 'react';
import { useLocalStorage, usePoll } from '../hooks';
import { healthApi } from '../api/client';
import { useTheme } from '../theme';
import { Card, btnGhost, btnPrimary } from '../components/ui';

export default function Settings() {
  const { theme, toggle } = useTheme();
  const [refresh, setRefresh] = useLocalStorage<number>('skyguard-refresh', 15000);
  const [apiUrl, setApiUrl] = useLocalStorage<string>('skyguard-api-url', '/api/v1');
  const [testResult, setTestResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const backend = usePoll(() => healthApi.service(), 30000);

  const testConnection = async () => {
    setBusy(true);
    try {
      const r = await healthApi.service();
      setTestResult(`OK — ${r.service} v${r.version} (${r.status}) at ${new Date().toLocaleTimeString()}`);
    } catch (e: unknown) {
      setTestResult(`FAILED — ${e instanceof Error ? e.message : 'unreachable'}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-enter space-y-4 p-4">
      <Card title="Appearance" subtitle="Dark-first command center; light mode for bright rooms">
        <div className="flex items-center gap-3 text-sm">
          <span>Current theme: <b>{theme}</b></span>
          <button className={btnPrimary} onClick={toggle}>Switch to {theme === 'dark' ? 'light' : 'dark'}</button>
        </div>
      </Card>

      <Card title="Data refresh" subtitle="Polling interval used across live pages">
        <div className="flex flex-wrap gap-2">
          {[5000, 15000, 30000, 60000].map((ms) => (
            <button
              key={ms}
              onClick={() => setRefresh(ms)}
              className={refresh === ms ? btnPrimary : btnGhost}
            >
              {ms / 1000}s
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-500">Stored locally. Pages reload on next visit with this cadence.</p>
      </Card>

      <Card
        title="Backend connection"
        subtitle={`Status: ${backend.data?.status ?? 'unknown'} · Version: ${backend.data?.version ?? '—'}`}
        action={<button disabled={busy} className={btnPrimary} onClick={testConnection}>{busy ? 'Testing…' : 'Test connection'}</button>}
      >
        <label className="text-xs">API base URL (applies after reload)
          <input
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="/api/v1"
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
          />
        </label>
        {testResult && <p className="mt-2 text-sm">{testResult}</p>}
        <p className="mt-2 text-xs text-slate-500">
          Dev proxy forwards <code>/api</code>, <code>/health</code> and <code>/ws</code> to the FastAPI backend on :8001.
          Set VITE_API_URL at build time to point elsewhere in production.
        </p>
      </Card>
    </div>
  );
}
