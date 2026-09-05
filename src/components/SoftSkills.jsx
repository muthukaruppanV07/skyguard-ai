import { BookOpen, Clock, Lightbulb, MessageSquare, RefreshCw, TrendingUp, Users } from "lucide-react";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import { SOFT_SKILLS } from "../data/softSkills";

const ICONS = {
  lightbulb: Lightbulb,
  users: Users,
  message: MessageSquare,
  clock: Clock,
  refresh: RefreshCw,
  book: BookOpen,
  trend: TrendingUp,
};

export default function SoftSkills() {
  return (
    <section id="soft-skills" className="section-pad relative bg-surface/40">
      <div className="container-x">
        <SectionHeading
          index="08"
          eyebrow="Soft Skills"
          title="How I work"
          subtitle="The behaviours that make me effective in teams and on real projects."
        />

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {SOFT_SKILLS.map((skill, i) => {
            const Icon = ICONS[skill.icon] || Lightbulb;
            return (
              <Reveal key={skill.label} delay={i % 4} className="h-full">
                <div className="group flex h-full flex-col items-center gap-3 rounded-2xl border border-white/[0.08] bg-card/80 p-6 text-center transition-all duration-300 hover:-translate-y-1 hover:border-cyan-400/40 hover:shadow-glow-soft">
                  <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.05] text-cyan-300 transition-transform duration-300 group-hover:scale-110">
                    <Icon className="h-6 w-6" />
                  </span>
                  <span className="text-sm font-semibold text-slate-200">{skill.label}</span>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}