import { ArrowUpRight, CheckCircle2, ExternalLink, Github, Sparkles, Star } from "lucide-react";
import { PROJECTS } from "../data/projects";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import cn from "../lib/cn";

function ProjectAction({ href, icon: Icon, label, primary = false }) {
  const isPlaceholder = href === "<placeholder>";
  return (
    <a
      href={isPlaceholder ? "#projects" : href}
      target={isPlaceholder ? undefined : "_blank"}
      rel="noopener noreferrer"
      title={isPlaceholder ? "Add the link in src/data/projects.js" : label}
      onClick={(e) => isPlaceholder && e.preventDefault()}
      className={cn(
        "inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all hover:-translate-y-0.5",
        primary
          ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-glow hover:brightness-110"
          : "border border-white/15 bg-white/[0.04] text-slate-200 hover:border-cyan-400/40 hover:text-cyan-300",
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </a>
  );
}

function FeaturedMock() {
  return (
    <div className="relative">
      <div className="rounded-2xl border border-white/10 bg-surface/80 p-5 shadow-glow backdrop-blur">
        <div className="mb-4 flex items-center justify-between border-b border-white/[0.06] pb-3">
          <span className="flex items-center gap-2 text-xs font-semibold text-slate-300">
            <Sparkles className="h-4 w-4 text-cyan-300" />
            AI Interview · Technical Mode
          </span>
          <span className="flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-2 py-1 text-[11px] font-medium text-emerald-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            Live feedback
          </span>
        </div>

        <div className="rounded-xl border border-white/[0.06] bg-card/70 p-4">
          <p className="font-mono text-xs text-slate-500">Question</p>
          <p className="mt-1 text-sm font-medium text-slate-200">
            “Explain Polymorphism with a clean Java example.”
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-md border border-cyan-400/20 bg-cyan-400/[0.06] px-2 py-1 font-mono text-[11px] text-cyan-200">
              OOP · Java
            </span>
            <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 font-mono text-[11px] text-slate-400">
              Difficulty: Medium
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <span className="inline-flex items-center gap-2 rounded-xl bg-white/[0.06] px-4 py-2 text-xs font-semibold text-slate-200">
            <span className="h-2 w-2 rounded-full bg-rose-400" /> Record Answer
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2 text-xs font-semibold text-white">
            Evaluate
          </span>
        </div>

        <div className="mt-4 flex items-center justify-between rounded-xl bg-emerald-400/[0.06] px-4 py-3">
          <span className="flex items-center gap-2 text-xs font-medium text-emerald-300">
            <CheckCircle2 className="h-4 w-4" />
            Performance evaluated · Weak areas highlighted
          </span>
          <span className="font-mono text-lg font-bold text-emerald-300">86%</span>
        </div>
      </div>

      <span className="pointer-events-none absolute -top-4 -right-3 animate-float text-2xl">
        <Star className="h-7 w-7 fill-amber-400 text-amber-400" />
      </span>
    </div>
  );
}

function FeatureList({ features }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {features.map((feature) => (
        <li key={feature} className="flex items-start gap-2 text-sm text-slate-300">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
          <span>{feature}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Projects() {
  return (
    <section id="projects" className="section-pad relative">
      <div className="container-x">
        <SectionHeading
          index="03"
          eyebrow="Projects"
          title="Things I've built"
          subtitle="Practical projects where I apply full-stack, database and AI concepts end to end."
        />

        {PROJECTS.map((project, i) => {
          const featured = !!project.featured;
          if (featured) {
            return (
              <Reveal key={project.title} className="mb-6">
                <div className="group relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-surface via-card to-surface p-6 shadow-2xl transition-all duration-300 hover:border-cyan-400/40 sm:p-10">
                  <div aria-hidden="true" className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-cyan-500/10 blur-[100px] transition-all duration-500 group-hover:bg-cyan-500/20" />
                  <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/60 to-transparent" />

                  <div className="relative grid items-center gap-10 lg:grid-cols-2">
                    <div>
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs font-semibold text-amber-300">
                        <Star className="h-3.5 w-3.5" />
                        Featured Project
                      </span>
                      <h3 className="mt-4 text-2xl font-bold text-white sm:text-3xl">
                        {project.title}
                      </h3>
                      <p className="mt-1 font-mono text-sm text-cyan-300">{project.subtitle}</p>
                      <p className="mt-4 leading-relaxed text-slate-400">{project.description}</p>

                      <div className="mt-5 flex flex-wrap gap-2">
                        {project.technologies.map((tech) => (
                          <span
                            key={tech}
                            className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1 font-mono text-xs text-slate-300"
                          >
                            {tech}
                          </span>
                        ))}
                      </div>

                      <div className="mt-6">
                        <FeatureList features={project.features} />
                      </div>

                      <div className="mt-7 flex flex-wrap gap-3">
                        <ProjectAction href={project.github} icon={Github} label="GitHub" primary />
                        <ProjectAction href={project.demo} icon={ExternalLink} label="Live Demo" />
                      </div>
                    </div>

                    <div className="lg:pl-4">
                      <FeaturedMock />
                    </div>
                  </div>
                </div>
              </Reveal>
            );
          }

          return (
            <Reveal key={project.title} delay={i % 2} className="mb-6">
              <div className="group h-full rounded-2xl border border-white/[0.08] bg-card/80 p-6 transition-all duration-300 hover:-translate-y-1 hover:border-blue-400/40 hover:shadow-glow sm:p-8">
                <div className="flex items-start justify-between gap-4">
                  <h3 className="text-xl font-bold text-white">{project.title}</h3>
                  <span className="rounded-lg border border-white/10 bg-white/[0.04] p-2 text-cyan-300">
                    <ArrowUpRight className="h-4 w-4" />
                  </span>
                </div>
                <p className="mt-1 font-mono text-sm text-blue-300">{project.subtitle}</p>
                <p className="mt-3 leading-relaxed text-slate-400">{project.description}</p>

                <div className="mt-5 flex flex-wrap gap-2">
                  {project.technologies.map((tech) => (
                    <span
                      key={tech}
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1 font-mono text-xs text-slate-300"
                    >
                      {tech}
                    </span>
                  ))}
                </div>

                <div className="mt-5">
                  <FeatureList features={project.features} />
                </div>

                <div className="mt-7 flex flex-wrap gap-3">
                  <ProjectAction href={project.github} icon={Github} label="GitHub" primary />
                  <ProjectAction href={project.demo} icon={ExternalLink} label="Live Demo" />
                </div>
              </div>
            </Reveal>
          );
        })}
      </div>
    </section>
  );
}