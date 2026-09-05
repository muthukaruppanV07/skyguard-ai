import { Trophy, Users } from "lucide-react";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import { ACHIEVEMENTS } from "../data/achievements";

export default function Achievements() {
  return (
    <section id="achievements" className="section-pad relative bg-surface/40">
      <div className="container-x">
        <SectionHeading
          index="06"
          eyebrow="Achievements"
          title="Highlights & wins"
          subtitle="Moments from college events, hackathons and team activities."
        />

        <Reveal>
          <div className="relative mx-auto mb-10 max-w-3xl overflow-hidden rounded-3xl border border-amber-400/25 bg-gradient-to-br from-amber-400/[0.08] via-card to-card p-7 text-center shadow-2xl sm:p-10">
            <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-400/60 to-transparent" />
            <div aria-hidden="true" className="absolute -top-20 left-1/2 h-48 w-48 -translate-x-1/2 rounded-full bg-amber-400/10 blur-[90px]" />

            <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-base shadow-glow">
              <Trophy className="h-8 w-8 text-base" />
            </span>
            <p className="mt-5 font-mono text-xs tracking-widest text-amber-300 uppercase">
              {ACHIEVEMENTS.featured.event}
            </p>
            <h3 className="mt-2 text-2xl font-extrabold text-white sm:text-3xl">
              {ACHIEVEMENTS.featured.title}
            </h3>
            <p className="mt-1 text-sm font-medium text-amber-200">{ACHIEVEMENTS.featured.subtitle}</p>
            <p className="mx-auto mt-4 max-w-lg text-sm text-slate-400 sm:text-base">
              {ACHIEVEMENTS.featured.description}
            </p>
          </div>
        </Reveal>

        <div className="grid gap-4 sm:grid-cols-2">
          {ACHIEVEMENTS.list.map((achievement, i) => (
            <Reveal key={achievement} delay={i % 2} className="h-full">
              <div className="flex h-full items-start gap-4 rounded-2xl border border-white/[0.08] bg-card/80 p-5 transition-all duration-300 hover:-translate-y-1 hover:border-cyan-400/40 hover:shadow-glow-soft">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.05] text-cyan-300">
                  <Users className="h-5 w-5" />
                </span>
                <p className="pt-1 text-sm leading-relaxed text-slate-300 sm:text-base">
                  {achievement}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}