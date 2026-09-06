"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import MapView from "@/components/MapView";
import type { MissingCase, GeoPoint } from "@/lib/types";

export default function MapPage() {
  const [cases, setCases] = useState<MissingCase[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<MissingCase[]>("/cases/public")
      .then(setCases)
      .catch((e) => setError(e.message));
  }, []);

  const points: GeoPoint[] = cases
    .filter((c) => typeof c.lastKnownLat === "number" && typeof c.lastKnownLng === "number")
    .map((c) => ({
      lat: c.lastKnownLat as number,
      lng: c.lastKnownLng as number,
      description: c.lastKnownPlace,
      capturedAt: c.lastKnownAt,
    }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-brand-ink">Public case map</h1>
        <p className="text-sm text-slate-500">
          Last-known locations of active public cases. Only non-sensitive details are shown.
        </p>
      </div>

      {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      <MapView
        points={points}
        label={(p) =>
          `<strong>Last seen near ${p.description ?? "unknown"}</strong>` +
          (p.capturedAt ? `<br/><small>${new Date(p.capturedAt).toLocaleString()}</small>` : "")
        }
      />

      {cases.length === 0 && !error && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-400">
          No public cases with coordinates right now.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cases.map((c) => (
          <div key={c.id} className="rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-sm">
            <p className="font-semibold text-brand-ink">
              {c.fullName || [c.firstName, c.lastName].filter(Boolean).join(" ")}
            </p>
            <p className="text-xs text-slate-400">{c.caseReference}</p>
            <p className="mt-1 text-slate-600">Last seen: {c.lastKnownPlace ?? "unknown"}</p>
            <p className="mt-1 text-xs text-slate-400">
              {c.lastKnownAt ? new Date(c.lastKnownAt).toLocaleString() : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
