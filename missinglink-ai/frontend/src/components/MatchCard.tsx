"use client";

import type { Match } from "@/lib/types";

const statusColor: Record<string, string> = {
  PENDING: "bg-amber-100 text-amber-800",
  REVIEWING: "bg-blue-100 text-blue-800",
  CONFIRMED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
};

function scoreBar(score: number) {
  const pct = Math.max(0, Math.min(100, score * 100));
  const color = score >= 0.8 ? "bg-green-500" : score >= 0.6 ? "bg-amber-500" : score >= 0.4 ? "bg-orange-500" : "bg-slate-300";
  return (
    <div className="h-2 w-full rounded-full bg-slate-100">
      <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function MatchCard({ item }: { item: Match }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-slate-500">{item.caseReference}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusColor[item.status] ?? "bg-slate-100 text-slate-600"}`}>
          {item.status}
        </span>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <span className="text-2xl font-black text-brand">
          {Math.round(item.overallScore * 100)}
          <span className="text-sm font-medium text-slate-400">%</span>
        </span>
        <div className="flex-1">{scoreBar(item.overallScore)}</div>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Sighting {item.sightingReference} · {new Date(item.createdAt).toLocaleString()}
      </p>
    </div>
  );
}
