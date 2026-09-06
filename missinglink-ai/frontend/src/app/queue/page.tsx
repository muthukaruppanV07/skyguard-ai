"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import RequireAuth from "@/components/RequireAuth";
import type { Match } from "@/lib/types";

interface MatchDetail {
  id: string;
  caseReference: string;
  sightingReference: string;
  overallScore: number;
  status: string;
  reviewedBy?: string;
  reviewNotes?: string;
  explanation: string[];
  limitations: string[];
  warning?: string;
}

const decisions = ["ACCEPT", "REJECT", "MORE_INFO", "DUPLICATE", "ESCALATE"];

function QueueBody() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [selected, setSelected] = useState<MatchDetail | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    api<Match[]>("/matches").then(setMatches).catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const open = async (id: number) => {
    const d = await api<MatchDetail>(`/matches/${id}`);
    setSelected(d);
    setNotes("");
  };

  const decide = async (decision: string) => {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const d = await api<MatchDetail>(`/matches/${selected.id}/decision`, {
        method: "PATCH",
        body: { decision, notes },
      });
      setSelected(d);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-brand-ink">Match review queue</h1>
        <p className="text-sm text-slate-500">
          AI-ranked leads. Nothing is acted on automatically — a human decides.
        </p>
      </div>

      {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-lg font-bold text-brand-ink">
            Leads ({matches.length})
          </h2>
          {matches.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-400">
              No leads yet. New sightings will appear here automatically.
            </p>
          ) : (
            <ul className="space-y-2">
              {matches.map((m) => (
                <li key={m.id}>
                  <button
                    onClick={() => open(m.id)}
                    className={`w-full rounded-xl border bg-white p-4 text-left shadow-sm transition hover:border-brand ${
                      selected?.id === String(m.id) ? "border-brand ring-1 ring-brand" : "border-slate-200"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-slate-500">{m.caseReference}</span>
                      <span className="text-sm font-black text-brand">
                        {Math.round(m.overallScore * 100)}%
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-400">
                      Sighting {m.sightingReference} · {new Date(m.createdAt).toLocaleString()}
                    </p>
                    <p className="mt-1 text-xs font-medium text-slate-500">Status: {m.status}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2 className="mb-3 text-lg font-bold text-brand-ink">Decision</h2>
          {!selected ? (
            <p className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-400">
              Select a lead to review its explanation and decide.
            </p>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-mono text-sm font-bold text-brand-ink">{selected.caseReference}</p>
                  <p className="text-xs text-slate-400">Sighting {selected.sightingReference}</p>
                </div>
                <span className="text-3xl font-black text-brand">
                  {Math.round(selected.overallScore * 100)}%
                </span>
              </div>

              <div className="mt-4">
                <h3 className="text-sm font-bold text-brand-ink">Why the AI ranked this</h3>
                {selected.explanation.map((line, i) => (
                  <p key={i} className="mt-1 text-sm text-slate-600">• {line}</p>
                ))}
                {selected.limitations.length > 0 && (
                  <>
                    <h3 className="mt-3 text-sm font-bold text-amber-700">Limitations</h3>
                    {selected.limitations.map((line, i) => (
                      <p key={i} className="mt-1 text-sm text-amber-700">• {line}</p>
                    ))}
                  </>
                )}
              </div>

              <div className="mt-4">
                <label className="text-sm font-medium text-slate-600">Review notes</label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Optional notes for the audit trail"
                />
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {decisions.map((d) => (
                  <button
                    key={d}
                    disabled={busy}
                    onClick={() => decide(d)}
                    className={`rounded-lg px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50 ${
                      d === "ACCEPT" ? "bg-green-600 hover:bg-green-700"
                      : d === "REJECT" ? "bg-red-600 hover:bg-red-700"
                      : d === "DUPLICATE" ? "bg-slate-500 hover:bg-slate-600"
                      : d === "ESCALATE" ? "bg-orange-500 hover:bg-orange-600"
                      : "bg-blue-500 hover:bg-blue-600"
                    }`}
                  >
                    {d.replace("_", " ")}
                  </button>
                ))}
              </div>

              {selected.reviewedBy && (
                <p className="mt-3 text-xs text-slate-400">
                  Reviewed by {selected.reviewedBy} — current status {selected.status}
                </p>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default function QueuePage() {
  return (
    <RequireAuth roles={["INVESTIGATOR", "ADMIN"]}>
      <QueueBody />
    </RequireAuth>
  );
}
