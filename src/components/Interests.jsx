import { Bot, Brain, Code2, Coffee, Globe, Layers } from "lucide-react";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import { INTERESTS } from "../data/softSkills";

const ICONS = {
  code: Code2,
  coffee: Coffee,
  globe: Globe,
  bot: Bot,
  layers: Layers,
  brain: Brain,
};

export default function Interests() {
  return (
    <section id="interests" className="section-pad relative">
      <div className="container-x">
        <SectionHeading
          index="09"
          eyebrow="Areas of Interest"
          title="What excites me"
          subtitle="The domains I want to grow into and keep building a career around."
        />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {INTERESTS.map((interest, i) => {
            const Icon = ICONS[interest.icon] || Code2;
            return (
              <Reveal key={interest.label} delay={i % 3} className="h-full">
                <div className="group flex items-center gap-4 rounded-2xl border border-white/[0.08] bg-card/80 p-5 transition-all duration-300 hover:-translate-y-1 hover:border-purple-400/40 hover:shadow-glow-soft">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500/15 to-cyan-400/15 text-purple-300">
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="font-semibold text-slate-200">{interest.label}</span>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}