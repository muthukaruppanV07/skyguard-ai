import { Brain, Code2, Database, Globe, Sparkles, Wrench } from "lucide-react";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import { SKILL_CATEGORIES } from "../data/skills";

const ICONS = {
  code: Code2,
  globe: Globe,
  database: Database,
  tools: Wrench,
  brain: Brain,
  sparkles: Sparkles,
};

const ACCENTS = {
  cyan: {
    icon: "text-cyan-300",
    ring: "group-hover:border-cyan-400/40 group-hover:shadow-glow",
    chip: "border-cyan-400/20 bg-cyan-400/[0.06] text-cyan-200",
  },
  blue: {
    icon: "text-blue-400",
    ring: "group-hover:border-blue-400/40 group-hover:shadow-glow",
    chip: "border-blue-400/20 bg-blue-400/[0.06] text-blue-200",
  },
  purple: {
    icon: "text-purple-400",
    ring: "group-hover:border-purple-400/40 group-hover:shadow-glow-soft",
    chip: "border-purple-400/20 bg-purple-400/[0.06] text-purple-200",
  },
  emerald: {
    icon: "text-emerald-400",
    ring: "group-hover:border-emerald-400/40 group-hover:shadow-glow",
    chip: "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-200",
  },
  amber: {
    icon: "text-amber-400",
    ring: "group-hover:border-amber-400/40 group-hover:shadow-glow",
    chip: "border-amber-400/20 bg-amber-400/[0.06] text-amber-200",
  },
  pink: {
    icon: "text-pink-400",
    ring: "group-hover:border-pink-400/40 group-hover:shadow-glow-soft",
    chip: "border-pink-400/20 bg-pink-400/[0.06] text-pink-200",
  },
};

export default function Skills() {
  return (
    <section id="skills" className="section-pad relative bg-surface/40">
      <div className="container-x">
        <SectionHeading
          index="02"
          eyebrow="My Skills"
          title="Technical Stack"
          subtitle="The languages, tools and concepts I use to build, connect and ship software."
        />

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {SKILL_CATEGORIES.map((category, i) => {
            const Icon = ICONS[category.icon] || Code2;
            const accent = ACCENTS[category.accent] || ACCENTS.cyan;
            return (
              <Reveal key={category.title} delay={i % 3} className="h-full">
                <div
                  className={`group h-full rounded-2xl border border-white/[0.08] bg-card/80 p-6 transition-all duration-300 hover:-translate-y-1 ${accent.ring}`}
                >
                  <div className="mb-5 flex items-center gap-3">
                    <span className={`flex h-11 w-11 items-center justify-center rounded-xl ${accent.icon} bg-white/[0.05]`}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <h3 className="text-lg font-semibold text-white">{category.title}</h3>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {category.skills.map((skill) => (
                      <span
                        key={skill}
                        className={`rounded-lg border px-3 py-1.5 font-mono text-xs transition-transform duration-200 group-hover:translate-x-0 hover:scale-105 ${accent.dot}`}
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>

        <Reveal className="mt-10">
          <div className="rounded-2xl border border-white/[0.08] bg-card/60 p-5 text-sm text-slate-400">
            <span className="font-semibold text-slate-200">Intentional about skill bars:</span>{" "}
            no fake percentages here. I list technology honestly and keep improving with real
            projects — the proof is in the code.
          </div>
        </Reveal>
      </div>
    </section>
  );
}