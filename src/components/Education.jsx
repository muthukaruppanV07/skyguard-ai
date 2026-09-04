import { Building2, CalendarDays, GraduationCap, MapPin } from "lucide-react";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import { EDUCATION } from "../data/education";

export default function Education() {
  return (
    <section id="education" className="section-pad relative">
      <div className="container-x">
        <SectionHeading
          index="07"
          eyebrow="Education"
          title="Academic background"
          subtitle="Where I'm pursuing my engineering degree and what I focus on."
        />

        <Reveal className="mx-auto max-w-3xl">
          <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-gradient-to-br from-card to-surface p-7 transition-all duration-300 hover:border-purple-400/40 hover:shadow-glow-soft sm:p-9">
            <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-purple-400/50 to-transparent" />

            <div className="flex items-start gap-5">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-500/20 to-cyan-400/20 text-purple-300">
                <GraduationCap className="h-7 w-7" />
              </span>

              <div className="min-w-0">
                <span className="inline-flex rounded-full border border-purple-400/20 bg-purple-400/[0.06] px-3 py-1 text-xs font-medium text-purple-200">
                  Undergraduate
                </span>
                <h3 className="mt-3 text-xl font-bold text-white sm:text-2xl">
                  {EDUCATION.degree}
                </h3>

                <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Building2 className="h-4 w-4 shrink-0 text-cyan-300" />
                    {EDUCATION.college}
                  </div>
                  <div className="flex items-center gap-2 text-slate-300">
                    <GraduationCap className="h-4 w-4 shrink-0 text-purple-300" />
                    {EDUCATION.university}
                  </div>
                  <div className="flex items-center gap-2 text-slate-300">
                    <MapPin className="h-4 w-4 shrink-0 text-blue-300" />
                    {EDUCATION.location}
                  </div>
                  <div className="flex items-center gap-2 text-slate-300">
                    <CalendarDays className="h-4 w-4 shrink-0 text-amber-300" />
                    Expected graduation · {EDUCATION.graduationYear}
                  </div>
                </div>

                <ul className="mt-5 space-y-2">
                  {EDUCATION.details.map((detail) => (
                    <li key={detail} className="flex items-start gap-2 text-sm text-slate-400">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gradient-to-r from-cyan-400 to-purple-400" />
                      {detail}
                    </li>
                  ))}
                </ul>

                {EDUCATION.cgpa && EDUCATION.cgpa !== "—" && (
                  <p className="mt-4 text-sm text-slate-400">
                    CGPA: <span className="font-semibold text-white">{EDUCATION.cgpa}</span>
                  </p>
                )}
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}