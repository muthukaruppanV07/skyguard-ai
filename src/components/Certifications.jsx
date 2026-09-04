import { Award, BadgeCheck, ExternalLink, Plus } from "lucide-react";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import { CERTIFICATIONS } from "../data/certifications";
import cn from "../lib/cn";

export default function Certifications() {
  return (
    <section id="certifications" className="section-pad relative">
      <div className="container-x">
        <SectionHeading
          index="05"
          eyebrow="Certifications & Learning"
          title="Credentials & continuous learning"
          subtitle="Certificates I've earned so far — plus placeholders I'll fill in as I complete more."
        />

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {CERTIFICATIONS.map((cert, i) => {
            const isPlaceholder = cert.status === "placeholder";
            return (
              <Reveal key={cert.title} delay={i % 3} className="h-full">
                <div
                  className={cn(
                    "group flex h-full flex-col rounded-2xl border bg-card/80 p-6 transition-all duration-300 hover:-translate-y-1",
                    isPlaceholder
                      ? "border-dashed border-white/15 opacity-80 hover:border-cyan-400/30"
                      : "border-white/[0.08] hover:border-cyan-400/40 hover:shadow-glow-soft",
                  )}
                >
                  <div className="mb-4 flex items-start justify-between">
                    <span
                      className={cn(
                        "flex h-11 w-11 items-center justify-center rounded-xl",
                        isPlaceholder
                          ? "bg-white/[0.05] text-slate-400"
                          : "bg-gradient-to-br from-cyan-400/15 to-purple-500/15 text-cyan-300",
                      )}
                    >
                      {isPlaceholder ? <Plus className="h-5 w-5" /> : <Award className="h-5 w-5" />}
                    </span>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold",
                        isPlaceholder
                          ? "border border-white/15 text-slate-400"
                          : "border border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300",
                      )}
                    >
                      <BadgeCheck className="h-3.5 w-3.5" />
                      {isPlaceholder ? "Add Certificate" : "Verified"}
                    </span>
                  </div>

                  <h3 className="text-base font-semibold text-white">{cert.title}</h3>
                  <p className="mt-1 text-sm text-slate-400">{cert.issuer}</p>

                  <div className="mt-auto pt-5">
                    {isPlaceholder ? (
                      <span className="text-xs text-slate-500">
                        Not yet earned — I'll add the credential here when it's ready.
                      </span>
                    ) : cert.credentialUrl ? (
                      <a
                        href={cert.credentialUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-sm font-medium text-cyan-300 transition-colors hover:text-cyan-200"
                      >
                        View credential <ExternalLink className="h-4 w-4" />
                      </a>
                    ) : (
                      <span className="text-xs text-slate-500">
                        Credential link can be added in src/data/certifications.js
                      </span>
                    )}
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}