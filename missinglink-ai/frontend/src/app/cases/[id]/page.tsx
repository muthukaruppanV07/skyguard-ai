"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import MatchCard from "@/components/MatchCard";
import MapView from "@/components/MapView";
import type { Match, TimelineEntry } from "@/lib/types";

interface CaseDetail {
  id: string;
  caseReference: string;
  status: string;
  priority: string;
  emergencyClassification?: string;
  firstName: string;
  lastName: string;
  age?: number;
  gender?: string;
  heightCm?: number;
  identificationMarks?: string;
  languages?: string;
  lastKnownPlace?: string;
  lastKnownAt?: string;
  lastKnownLat?: number;
  lastKnownLng?: number;
  description?: string;
  isPublic: boolean;
  timeline: TimelineEntry[];
  profile?: {
    hair?: string;
    eyes?: string;
    skinTone?: string;
    clothing?: string;
    accessories?: string;
    backpack?: string;
    shoes?: string;
  };
  photos: string[];
}

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<CaseDetail>(`/cases/${params.id}`)
      .then((d) => {
        setDetail(d);
        return api<Match[]>(`/matches?caseId=${params.id}`).catch(() => [] as Match[]);
      })
      .then(setMatches)
      .catch((e) => setError(e.message));
  }, [params.id]);

  if (error) {
    return <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>;
  }
  if (!detail) {
    return <p className="py-16 text-center text-slate-400">Loading case…</p>;
  }

  const fullName = `${detail.firstName} ${detail.lastName}`;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs text-slate-400">{detail.caseReference}</p>
          <h1 className="text-3xl font-black text-brand-ink">{fullName}</h1>
          <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold">
            <span className="rounded-full bg-brand-ink px-3 py-1 text-white">{detail.status}</span>
            <span className="rounded-full bg-amber-400 px-3 py-1 text-brand-ink">{detail.priority} priority</span>
          </div>
          {detail.emergencyClassification && (
            <p className="mt-2 text-sm text-slate-500">
              Triage: <span className="font-medium">{detail.emergencyClassification}</span>
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-brand-ink">Profile</h2>
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-400">Age</dt>
            <dd>{detail.age ?? "unknown"}</dd>
            <dt className="text-slate-400">Gender</dt>
            <dd>{detail.gender?.toLowerCase() ?? "unknown"}</dd>
            <dt className="text-slate-400">Height</dt>
            <dd>{detail.heightCm ? `${detail.heightCm} cm` : "unknown"}</dd>
            <dt className="text-slate-400">Languages</dt>
            <dd>{detail.languages ?? "unknown"}</dd>
            <dt className="text-slate-400">Identification marks</dt>
            <dd>{detail.identificationMarks ?? "none"}</dd>
            <dt className="text-slate-400">Hair / Eyes</dt>
            <dd>
              {detail.profile?.hair ?? "unknown"} / {detail.profile?.eyes ?? "unknown"}
            </dd>
            <dt className="text-slate-400">Clothing</dt>
            <dd>{detail.profile?.clothing ?? "unknown"}</dd>
            <dt className="text-slate-400">Accessories</dt>
            <dd>{detail.profile?.accessories ?? "unknown"}</dd>
          </dl>
          {detail.description && (
            <p className="mt-4 border-t border-slate-100 pt-4 text-sm text-slate-600">{detail.description}</p>
          )}
        </div>

        <div className="space-y-6">
          {typeof detail.lastKnownLat === "number" && typeof detail.lastKnownLng === "number" ? (
            <MapView
              points={[{ lat: detail.lastKnownLat, lng: detail.lastKnownLng }]}
              zoom={13}
              label={() => `<strong>Last known location</strong>`}
            />
          ) : (
            <div className="flex h-32 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-sm text-slate-400">
              No coordinates available
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-bold text-brand-ink">Timeline</h2>
            <ol className="mt-3 space-y-3">
              {detail.timeline.map((t) => (
                <li key={t.eventType + t.createdAt} className="flex gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand" />
                  <div>
                    <p className="text-sm font-medium text-brand-ink">{t.eventType}</p>
                    <p className="text-xs text-slate-400">
                      {t.actorName ?? "System"} · {new Date(t.createdAt).toLocaleString()}
                    </p>
                    {t.description && <p className="mt-1 text-sm text-slate-600">{t.description}</p>}
                  </div>
                </li>
              ))}
              {detail.timeline.length === 0 && (
                <li className="text-sm text-slate-400">No timeline events yet.</li>
              )}
            </ol>
          </div>
        </div>
      </div>

      {matches.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-bold text-brand-ink">Match leads</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {matches.map((m) => (
              <MatchCard key={m.id} item={m} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
