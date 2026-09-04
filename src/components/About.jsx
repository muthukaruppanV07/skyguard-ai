import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";
import { PROFILE } from "../data/config";

export default function About() {
  return (
    <section id="about" className="section-pad relative">
      <div className="container-x">
        <SectionHeading
          index="01"
          eyebrow="About Me"
          title="Turning ideas into software"
          subtitle="A quick look at who I am, what I do and where I'm headed."
        />

        <div className="grid gap-10 lg:grid-cols-5 lg:gap-14">
          <Reveal className="lg:col-span-3">
            <div className="space-y-4 text-base leading-relaxed text-slate-400 sm:text-lg">
              {PROFILE.aboutParagraphs.map((paragraph, i) => (
                <p key={i}>{paragraph}</p>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap gap-3">
              <span className="rounded-full border border-cyan-400/20 bg-cyan-400/[0.06] px-4 py-2 text-sm font-medium text-cyan-300">
                Open to internships
              </span>
              <span className="rounded-full border border-purple-400/20 bg-purple-400/[0.06] px-4 py-2 text-sm font-medium text-purple-300">
                Java Full-Stack track
              </span>
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-300">
                Remote-friendly
              </span>
            </div>
          </Reveal>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:col-span-2 lg:grid-cols-2">
            {PROFILE.highlightCards.map((card, i) => (
              <Reveal key={card.label} delay={i % 4} className="h-full">
                <div className="group flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-white/[0.08] bg-card/80 p-5 text-center transition-all duration-300 hover:-translate-y-1 hover:border-cyan-400/40 hover:shadow-glow-soft">
                  <span className="text-3xl transition-transform duration-300 group-hover:scale-110">
                    {card.emoji}
                  </span>
                  <span className="text-sm font-medium leading-snug text-slate-200">
                    {card.label}
                  </span>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}