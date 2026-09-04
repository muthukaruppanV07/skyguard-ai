import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="space-y-10">
      <section className="rounded-3xl bg-brand-ink px-6 py-14 text-white">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-4xl font-black tracking-tight">
            Help bring someone home.
          </h1>
          <p className="mt-4 text-lg text-blue-100">
            MissingLink connects the public with investigators through
            AI-assisted matching — report a missing person, submit a sighting
            with a photo, and get a transparent lead queue in minutes.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/report" className="rounded-lg bg-amber-400 px-6 py-3 font-bold text-brand-ink hover:bg-amber-300">
              Report a missing person
            </Link>
            <Link href="/sighting" className="rounded-lg bg-white/10 px-6 py-3 font-semibold text-white ring-1 ring-white/30 hover:bg-white/20">
              Submit a sighting
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {[
          {
            title: "Report in minutes",
            body: "A guided form captures what matters: description, last known location, and a photo. The case becomes public instantly.",
          },
          {
            title: "AI-assisted matching",
            body: "Photo quality, face, clothing, location and time are scored against active cases — with plain-English explanations and confidence limits.",
          },
          {
            title: "Investigators stay in control",
            body: "No automated actions. Investigators review a ranked queue, confirm or reject each lead, and the public sees honest status.",
          },
        ].map((c) => (
          <div key={c.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="font-bold text-brand-ink">{c.title}</h3>
            <p className="mt-2 text-sm text-slate-500">{c.body}</p>
          </div>
        ))}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
        <h2 className="font-bold text-brand-ink">Privacy & safety principles</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Biometric data is never shared with the public — only lead notifications.</li>
          <li>All case data is encrypted at rest; photo uploads are malware-scanned.</li>
          <li>Every model decision explains itself and lists its limitations.</li>
          <li>Sensitive data access is role-based and fully audited.</li>
        </ul>
      </section>
    </div>
  );
}
