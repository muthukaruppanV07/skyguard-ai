"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

interface CaseCreated {
  id: string;
  caseReference: string;
  status: string;
  priority: string;
}

export default function ReportPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<CaseCreated | null>(null);

  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    age: "",
    sex: "MALE",
    heightCm: "",
    eyeColour: "",
    distinguishingFeatures: "",
    lastSeenClothing: "",
    lastKnownLocation: "",
    lastKnownAt: "",
    isPublic: true,
    isAtRisk: false,
    hasSafeguardingConcerns: false,
  });

  const set = (k: keyof typeof form, v: string | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api<CaseCreated>("/cases", {
        method: "POST",
        body: {
          firstName: form.firstName,
          lastName: form.lastName,
          age: form.age ? Number(form.age) : null,
          sex: form.sex,
          heightCm: form.heightCm ? Number(form.heightCm) : null,
          eyeColour: form.eyeColour || null,
          distinguishingFeatures: form.distinguishingFeatures || null,
          lastSeenClothing: form.lastSeenClothing || null,
          lastKnownLocation: form.lastKnownLocation || null,
          lastKnownAt: form.lastKnownAt ? new Date(form.lastKnownAt).toISOString() : null,
          isPublic: form.isPublic,
          isAtRisk: form.isAtRisk,
          hasSafeguardingConcerns: form.hasSafeguardingConcerns,
        },
      });
      setCreated(res);
      setTimeout(() => router.push("/map"), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create case");
    } finally {
      setBusy(false);
    }
  };

  if (created) {
    return (
      <div className="mx-auto max-w-xl rounded-2xl border border-green-200 bg-green-50 p-8 text-center">
        <h1 className="text-xl font-bold text-green-800">Case registered</h1>
        <p className="mt-2 text-green-700">
          Reference <span className="font-mono font-bold">{created.caseReference}</span> — priority{" "}
          <span className="font-bold">{created.priority}</span>. It is now visible to
          investigators and the public. Redirecting…
        </p>
      </div>
    );
  }

  const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";
  const label = "text-sm font-medium text-slate-600";

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold text-brand-ink">Report a missing person</h1>
      <p className="mt-1 text-sm text-slate-500">
        If someone is in immediate danger, call your local emergency number first.
      </p>
      <form onSubmit={submit} className="mt-6 space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={label}>First name</label>
            <input className={input} required value={form.firstName} onChange={(e) => set("firstName", e.target.value)} />
          </div>
          <div>
            <label className={label}>Last name</label>
            <input className={input} required value={form.lastName} onChange={(e) => set("lastName", e.target.value)} />
          </div>
          <div>
            <label className={label}>Age</label>
            <input type="number" min={0} className={input} value={form.age} onChange={(e) => set("age", e.target.value)} />
          </div>
          <div>
            <label className={label}>Sex</label>
            <select className={input} value={form.sex} onChange={(e) => set("sex", e.target.value)}>
              <option value="MALE">Male</option>
              <option value="FEMALE">Female</option>
              <option value="OTHER">Other / unknown</option>
            </select>
          </div>
          <div>
            <label className={label}>Height (cm)</label>
            <input type="number" min={0} className={input} value={form.heightCm} onChange={(e) => set("heightCm", e.target.value)} />
          </div>
          <div>
            <label className={label}>Eye colour</label>
            <input className={input} value={form.eyeColour} onChange={(e) => set("eyeColour", e.target.value)} />
          </div>
        </div>

        <div>
          <label className={label}>Distinguishing features</label>
          <textarea className={input} rows={2} value={form.distinguishingFeatures} onChange={(e) => set("distinguishingFeatures", e.target.value)} />
        </div>
        <div>
          <label className={label}>Clothing last seen in</label>
          <input className={input} value={form.lastSeenClothing} onChange={(e) => set("lastSeenClothing", e.target.value)} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={label}>Last known location</label>
            <input className={input} placeholder="e.g. near Bengaluru city market" value={form.lastKnownLocation} onChange={(e) => set("lastKnownLocation", e.target.value)} />
          </div>
          <div>
            <label className={label}>Last seen date & time</label>
            <input type="datetime-local" className={input} value={form.lastKnownAt} onChange={(e) => set("lastKnownAt", e.target.value)} />
          </div>
        </div>

        <div className="space-y-2 rounded-lg bg-slate-50 p-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.isPublic} onChange={(e) => set("isPublic", e.target.checked)} />
            Public case — visible to the community
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.isAtRisk} onChange={(e) => set("isAtRisk", e.target.checked)} />
            Vulnerable / at risk (raises priority)
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.hasSafeguardingConcerns} onChange={(e) => set("hasSafeguardingConcerns", e.target.checked)} />
            Safeguarding concerns (restricts public details)
          </label>
        </div>

        {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-brand px-4 py-3 font-semibold text-white hover:bg-brand-dark disabled:opacity-50"
        >
          {busy ? "Registering…" : "Register missing person"}
        </button>
      </form>
    </div>
  );
}
