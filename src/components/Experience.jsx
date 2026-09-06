import { Briefcase, CheckCircle2, Cloud, Rocket } from "lucide-react";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import { EXPERIENCES } from "../data/experience";
import cn from "../lib/cn";

const ICONS = { cloud: Cloud, rocket: Rocket };

const ACCENTS = {
  cyan: {
    dot: "border-cyan-400/40 bg-cyan-400/10 text-cyan-300",
    line: "bg-gradient-to-b from-cyan-400/50 to-blue-500/20",
    badge: "border-cyan-400/20 bg-cyan-400/[0.06] text-cyan-200",
  },
  purple: {
    dot: "border-purple-400/40 bg-purple-400/10 text-purple-300",
    line: "bg-gradient-to-b from-purple-400/50 to-cyan-400/20",
    badge: "border-purple-400/20 bg-purple-400/[0.06] text-purple-200",
  },
};

export default function Experience() {
  return (
    <section id="experience" className="section-pad relative bg-surface/40">
      <div className="container-x">
        <SectionHeading
          index="04"
          eyebrow="Experience"
          title="Internships & programs"
          subtitle="Virtual experience and learning programs that shaped how I build and communicate software."
        />

        <div className="relative mx-auto max-w-3xl">
          <span aria-hidden="true" className="absolute left-5 top-2 bottom-2 hidden w-px bg-white/[0.08] sm:block" />

          <div className="space-y-10">
            {EXPERIENCES.map((experience, i) => {
              const Icon = ICONS[experience.icon] || Briefcase;
              const accent = ACCENTS[experience.accent] || ACCENTS.cyan;
              return (
                <Reveal key={experience.company} delay={i} className="relative">
                  <div className="flex gap-5">
                    <div className="relative hidden shrink-0 sm:block">
                      <span className={cn("absolute left-0 top-0 z-10 flex h-11 w-11 items-center justify-center rounded-xl border", accent.dot)}>
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="absolute left-5 top-11 h-full w-px -translate-x-1/2 bg-white/[0.08]" />
                    </div>

                    <div className="flex-1 rounded-2xl border border-white/[0.08] bg-card/80 p-6 transition-all duration-300 hover:-translate-y-1 hover:border-white/20 sm:p-7">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <h3 className="flex items-center gap-2 text-lg font-bold text-white sm:text-xl">
                          <Icon className="h-5 w-5 text-cyan-300" />
                          {experience.company}
                        </h3>
                        <p className="font-mono text-sm text-cyan-300">{experience.role}</p>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className={cn("rounded-full border px-3 py-1 text-xs font-medium", accent.badge)}>
                          {experience.type}
                        </span>
                        <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-slate-300">
                          {experience.platform}
                        </span>
                      </div>

                      <p className="mt-4 text-sm text-slate-400 sm:text-base">{experience.summary}</p>

                      <ul className="mt-5 space-y-2.5">
                        {experience.points.map((point) => (
                          <li key={point} className="flex items-start gap-2.5 text-sm text-slate-300">
                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
                            <span>{point}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}