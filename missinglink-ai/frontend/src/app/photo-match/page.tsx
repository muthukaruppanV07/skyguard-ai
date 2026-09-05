"use client";

import { useState } from "react";
import { apiForm } from "@/lib/api";
import PhotoUpload from "@/components/PhotoUpload";
import RequireAuth from "@/components/RequireAuth";

interface FaceMatch {
  caseId: string;
  caseReference: string;
  fullName: string;
  status: string;
  matchScore: number;
  faceSimilarity: number;
  imageSimilarity: number;
  signalWeights: Record<string, number>;
  explanation: string;
  limitations: string[];
  recommendation: string;
}

interface FaceMatchResult {
  faceDetected: boolean;
  qualityScore: number;
  qualityFlags: string[];
  matches: FaceMatch[];
  model: string;
  threshold: number;
  processingTimeMs: number;
  warning: string;
}

function scoreColor(v: number) {
  if (v >= 0.75) return "bg-red-600";
  if (v >= 0.55) return "bg-orange-500";
  if (v >= 0.4) return "bg-amber-400";
  return "bg-slate-400";
}

function FaceMatchForm() {
  const [photo, setPhoto] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<FaceMatchResult | null>(null);

  const runMatch = async () => {
    if (!photo) {
      setError("Add a photo first.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const fd = new FormData();
      const blob = await (await fetch(photo)).blob();
      fd.append("photo", blob, "face-photo.jpg");
      setResult(await apiForm<FaceMatchResult>("/photo-match", fd));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Matching failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold text-brand-ink">Face match</h1>
      <p className="mt-1 text-sm text-slate-500">
        Upload a photo of a person and our AI ranks them against active case profiles by face
        and appearance. Matches are possible leads — never an identity claim.
      </p>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <PhotoUpload onChange={setPhoto} />
        <button
          onClick={runMatch}
          disabled={busy || !photo}
          className="mt-4 w-full rounded-lg bg-brand px-4 py-3 font-semibold text-white hover:bg-brand-dark disabled:opacity-50"
        >
          {busy ? "Analyzing face…" : "Find matches"}
        </button>
        {error && <p className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      </div>

      {result && (
        <div className="mt-6 space-y-4">
          {result.warning && (
            <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">{result.warning}</p>
          )}
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span className="rounded-full bg-slate-100 px-3 py-1">
              Face detected: <b>{result.faceDetected ? "yes" : "no"}</b>
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1">
              Quality: <b>{Math.round(result.qualityScore * 100)}%</b>
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1">Model: {result.model}</span>
            {result.matches.length === 0 && (
              <span className="rounded-full bg-slate-100 px-3 py-1">
                No matches above {Math.round(result.threshold * 100)}%
              </span>
            )}
          </div>

          {result.matches.map((m) => (
            <div key={m.caseId} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-mono text-xs text-slate-400">{m.caseReference}</p>
                  <h3 className="text-lg font-bold text-brand-ink">{m.fullName}</h3>
                  <p className="text-xs text-slate-400">{m.status}</p>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-black text-brand">{Math.round(m.matchScore * 100)}%</div>
                  <div className="text-xs text-slate-400">match</div>
                </div>
              </div>

              <div className="mt-3 h-2 w-full rounded-full bg-slate-100">
                <div
                  className={`h-2 rounded-full ${scoreColor(m.matchScore)}`}
                  style={{ width: `${Math.min(100, m.matchScore * 100)}%` }}
                />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <div className="rounded-lg bg-slate-50 p-2">
                  <p className="text-xs text-slate-400">Face</p>
                  <p className="font-semibold">{Math.round(m.faceSimilarity * 100)}%</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-2">
                  <p className="text-xs text-slate-400">Image</p>
                  <p className="font-semibold">{Math.round(m.imageSimilarity * 100)}%</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-2">
                  <p className="text-xs text-slate-400">Recommendation</p>
                  <p className="text-xs font-medium leading-tight">{m.recommendation}</p>
                </div>
              </div>

              {m.explanation && (
                <p className="mt-3 text-sm text-slate-600">{m.explanation}</p>
              )}
              {m.limitations.length > 0 && (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-400">
                  {m.limitations.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PhotoMatchPage() {
  return (
    <RequireAuth>
      <FaceMatchForm />
    </RequireAuth>
  );
}