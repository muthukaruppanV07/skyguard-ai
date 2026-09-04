"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiForm } from "@/lib/api";
import PhotoUpload from "@/components/PhotoUpload";
import RequireAuth from "@/components/RequireAuth";

interface SightingOutcome {
  sightingReference: string;
  status: string;
  evidenceClusterId?: number | null;
}

function SightingForm() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [photo, setPhoto] = useState("");
  const [located, setLocated] = useState(false);
  const [result, setResult] = useState<SightingOutcome | null>(null);

  const [form, setForm] = useState({
    description: "",
    clothing: "",
    directionOfMovement: "",
    vehicleInfo: "",
    notes: "",
    locationName: "",
    lat: "",
    lng: "",
    capturedAt: "",
    source: "MOBILE_WEB",
  });

  const set = (k: keyof typeof form, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));

  const locate = () => {
    if (!navigator.geolocation) {
      setError("Geolocation is not available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm((f) => ({
          ...f,
          lat: pos.coords.latitude.toFixed(6),
          lng: pos.coords.longitude.toFixed(6),
        }));
        setLocated(true);
      },
      () => setError("Could not get your location — you can type it instead."),
    );
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const fd = new FormData();
      if (photo) {
        const blob = await (await fetch(photo)).blob();
        fd.append("photo", blob, "sighting-photo.jpg");
      }
      fd.append("description", form.description);
      fd.append("clothing", form.clothing);
      fd.append("directionOfMovement", form.directionOfMovement);
      fd.append("vehicleInfo", form.vehicleInfo);
      fd.append("notes", form.notes);
      fd.append("locationName", form.locationName);
      fd.append("lat", form.lat);
      fd.append("lng", form.lng);
      fd.append("source", form.source);
      if (form.capturedAt) {
        fd.append("capturedAt", new Date(form.capturedAt).toISOString());
      }
      const res = await apiForm<SightingOutcome>("/sightings", fd);
      setResult(res);
      setTimeout(() => router.push("/map"), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <div className="mx-auto max-w-xl rounded-2xl border border-green-200 bg-green-50 p-8 text-center">
        <h1 className="text-xl font-bold text-green-800">Sighting submitted</h1>
        <p className="mt-2 text-green-700">
          Reference <span className="font-mono font-bold">{result.sightingReference}</span> — status{" "}
          <span className="font-bold">{result.status}</span>. Our matching engine is checking it
          against active cases. Redirecting to the map…
        </p>
      </div>
    );
  }

  const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";
  const label = "text-sm font-medium text-slate-600";

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold text-brand-ink">Submit a sighting</h1>
      <p className="mt-1 text-sm text-slate-500">
        If you saw someone who might match a missing person, share the details.
        A photo helps our AI rank leads — it is never shown publicly.
      </p>
      <form onSubmit={submit} className="mt-6 space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <PhotoUpload onChange={setPhoto} />

        <div>
          <label className={label}>What did you see?</label>
          <textarea className={input} rows={3} value={form.description}
            onChange={(e) => set("description", e.target.value)}
            placeholder="e.g. a person matching the poster was walking south along the market road" />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={label}>Clothing seen</label>
            <input className={input} value={form.clothing} onChange={(e) => set("clothing", e.target.value)} />
          </div>
          <div>
            <label className={label}>Direction of movement</label>
            <input className={input} value={form.directionOfMovement} onChange={(e) => set("directionOfMovement", e.target.value)} />
          </div>
          <div>
            <label className={label}>Vehicle info (if any)</label>
            <input className={input} value={form.vehicleInfo} onChange={(e) => set("vehicleInfo", e.target.value)} />
          </div>
          <div>
            <label className={label}>Date & time seen</label>
            <input type="datetime-local" className={input} value={form.capturedAt} onChange={(e) => set("capturedAt", e.target.value)} />
          </div>
        </div>

        <div>
          <label className={label}>Location</label>
          <div className="mt-1 flex gap-2">
            <input className="flex-1 rounded-lg border border-slate-300 px-3 py-2" placeholder="e.g. near bus stop 4, MG Road"
              value={form.locationName} onChange={(e) => set("locationName", e.target.value)} />
            <button type="button" onClick={locate} className="rounded-lg bg-slate-100 px-3 text-sm font-medium text-brand hover:bg-slate-200">
              Use my location
            </button>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <input className="rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Latitude" value={form.lat}
              onChange={(e) => set("lat", e.target.value)} />
            <input className="rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Longitude" value={form.lng}
              onChange={(e) => set("lng", e.target.value)} />
          </div>
          {located && <p className="mt-1 text-xs text-green-600">Location captured from your device.</p>}
        </div>

        <div>
          <label className={label}>Notes for investigators</label>
          <textarea className={input} rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
        </div>

        {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

        <button type="submit" disabled={busy}
          className="w-full rounded-lg bg-brand px-4 py-3 font-semibold text-white hover:bg-brand-dark disabled:opacity-50">
          {busy ? "Submitting…" : "Submit sighting"}
        </button>
      </form>
    </div>
  );
}

export default function SightingPage() {
  return (
    <RequireAuth>
      <SightingForm />
    </RequireAuth>
  );
}
