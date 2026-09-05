"use client";

import type { MissingCase } from "@/lib/types";

const priorityColor: Record<string, string> = {
  CRITICAL: "bg-red-600",
  HIGH: "bg-orange-500",
  STANDARD: "bg-slate-400",
};

export default function CaseCard({ item }: { item: MissingCase }) {
  const fullName = item.fullName || [item.firstName, item.lastName].filter(Boolean).join(" ");
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-brand-ink">{fullName}</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs font-bold text-white ${priorityColor[item.priority] ?? "bg-slate-400"}`}>
          {item.priority}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        {item.age ? `${item.age} years` : "Age unknown"}
        {item.sex ? `, ${item.sex.toLowerCase()}` : item.gender ? `, ${item.gender.toLowerCase()}` : ""}
      </p>
      <p className="mt-1 text-sm text-slate-600">
        Last seen: {item.lastKnownLocation ?? item.lastKnownPlace ?? "unknown"}
      </p>
      <p className="mt-1 text-xs text-slate-400">
        {item.lastKnownAt ? new Date(item.lastKnownAt).toLocaleString() : ""}
      </p>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-600">{item.id}</span>
        <span className={`font-semibold ${item.status === "RESOLVED" ? "text-green-600" : "text-brand"}`}>
          {item.status}
        </span>
      </div>
    </div>
  );
}
