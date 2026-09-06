import { Github, Heart, Linkedin, Mail } from "lucide-react";
import { PROFILE } from "../data/config";

const links = [
  { label: "LinkedIn", href: PROFILE.linkedin, icon: Linkedin },
  { label: "GitHub", href: PROFILE.github, icon: Github },
  { label: "Email", href: `mailto:${PROFILE.email}`, icon: Mail },
];

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.06] bg-surface/60">
      <div className="container-x py-12">
        <div className="flex flex-col items-center gap-6 text-center md:flex-row md:justify-between md:text-left">
          <div>
            <p className="flex items-center justify-center gap-2 text-lg font-bold text-white md:justify-start">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-purple-500 font-mono text-xs font-bold text-base">
                MV
              </span>
              {PROFILE.name}
            </p>
            <p className="mt-1 text-sm text-slate-400">{PROFILE.titleLine}</p>
          </div>

          <div className="flex items-center gap-3">
            {links.map((link) => {
              const Icon = link.icon;
              return (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={link.label}
                  title={link.label}
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300 transition-all hover:-translate-y-0.5 hover:border-cyan-400/40 hover:text-cyan-300 hover:shadow-glow"
                >
                  <Icon className="h-4 w-4" />
                </a>
              );
            })}
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-white/[0.06] pt-6 text-center text-xs text-slate-500 sm:flex-row sm:text-left">
          <p>© 2026 {PROFILE.nameShort}. All rights reserved.</p>
          <p className="font-mono">
            Built with React · Tailwind CSS · Framer Motion
          </p>
        </div>
      </div>
    </footer>
  );
}