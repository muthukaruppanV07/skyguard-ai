import { motion } from "framer-motion";
import { ArrowRight, Download, Github, Linkedin, Mail, MapPin } from "lucide-react";
import { PROFILE } from "../data/config";

const container = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.12 } },
};

const item = {
  hidden: { opacity: 0, y: 22 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const CODE_LINES = [
  { indent: 0, parts: [
    { c: "text-purple-300", t: "const" },
    { c: "text-slate-200", t: " profile" },
    { c: "text-slate-500", t: " = {" },
  ] },
  { indent: 1, parts: [
    { c: "text-fuchsia-300", t: "name" },
    { c: "text-slate-500", t: ": " },
    { c: "text-amber-300", t: "'Muthukaruppan V'" },
    { c: "text-slate-500", t: "," },
  ] },
  { indent: 1, parts: [
    { c: "text-fuchsia-300", t: "role" },
    { c: "text-slate-500", t: ": " },
    { c: "text-amber-300", t: "'Full-Stack Developer'" },
    { c: "text-slate-500", t: "," },
  ] },
  { indent: 1, parts: [
    { c: "text-fuchsia-300", t: "stack" },
    { c: "text-slate-500", t: ": " },
    { c: "text-amber-300", t: "['Java','React','Spring Boot']" },
    { c: "text-slate-500", t: "," },
  ] },
  { indent: 1, parts: [
    { c: "text-fuchsia-300", t: "learning" },
    { c: "text-slate-500", t: ": " },
    { c: "text-amber-300", t: "'REST APIs','AI/ML'" },
    { c: "text-slate-500", t: "," },
  ] },
  { indent: 1, parts: [
    { c: "text-fuchsia-300", t: "openToWork" },
    { c: "text-slate-500", t: ": " },
    { c: "text-emerald-400", t: "true" },
    { c: "text-slate-500", t: "," },
  ] },
  { indent: 0, parts: [{ c: "text-slate-300", t: "};" }] },
  { indent: 0, parts: [{ c: "text-slate-600", t: "// keep building. keep learning." }] },
];

const FLOATING_CHIPS = [
  { label: "Java", className: "left-4 -top-5", delay: "0s" },
  { label: "React", className: "right-2 top-10", delay: "0.4s" },
  { label: "Spring Boot", className: "-bottom-5 left-1", delay: "0.2s" },
  { label: "SQL", className: "right-6 -bottom-4", delay: "0.6s" },
];

function SocialLink({ href, label, icon: Icon }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
      title={label}
      className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300 transition-all hover:-translate-y-0.5 hover:border-cyan-400/40 hover:text-cyan-300 hover:shadow-glow"
    >
      <Icon className="h-5 w-5" />
    </a>
  );
}

function CodeWindow() {
  return (
    <div className="relative">
      <div className="animate-float-slow rounded-2xl border border-white/10 bg-surface/80 p-5 shadow-glow backdrop-blur-xl">
        <div className="mb-4 flex items-center gap-2 border-b border-white/[0.06] pb-3">
          <span className="h-3 w-3 rounded-full bg-rose-500/80" />
          <span className="h-3 w-3 rounded-full bg-amber-400/80" />
          <span className="h-3 w-3 rounded-full bg-emerald-400/80" />
          <span className="ml-3 font-mono text-xs text-slate-500">developer.js</span>
        </div>
        <pre className="overflow-x-auto font-mono text-[12.5px] leading-7 text-slate-400 sm:text-sm">
          {CODE_LINES.map((line, i) => (
            <div key={i} className="whitespace-pre">
              {line.indent > 0 && "  ".repeat(line.indent)}
              {line.parts.map((part, j) => (
                <span key={j} className={part.c}>
                  {part.t}
                </span>
              ))}
            </div>
          ))}
        </pre>
      </div>

      <span className="pointer-events-none absolute -top-6 -right-3 font-mono text-4xl text-cyan-400/15 sm:text-5xl">
        {`</>`}
      </span>
      <span className="pointer-events-none absolute -bottom-6 -left-4 font-mono text-4xl text-purple-400/15 sm:text-5xl">
        {"{}"}
      </span>

      {FLOATING_CHIPS.map((chip) => (
        <span
          key={chip.label}
          style={{ animationDelay: chip.delay }}
          className={`absolute animate-float rounded-xl border border-white/10 bg-surface/90 px-3 py-1.5 font-mono text-xs font-medium text-cyan-200 shadow-lg backdrop-blur ${chip.className}`}
        >
          {chip.label}
        </span>
      ))}
    </div>
  );
}

export default function Hero() {
  const resumeHref = PROFILE.resumeUrl
    ? { href: PROFILE.resumeUrl, download: "" }
    : { href: "#contact" };

  return (
    <section id="home" className="relative flex min-h-screen items-center overflow-hidden pt-24 pb-16">
      {/* Background */}
      <div aria-hidden="true" className="absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-grid [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />
        <div className="absolute -top-32 left-1/4 h-96 w-96 rounded-full bg-cyan-500/20 blur-[120px]" />
        <div className="absolute top-1/3 -right-32 h-96 w-96 rounded-full bg-purple-500/20 blur-[120px]" />
        <div className="absolute bottom-0 left-0 h-72 w-72 rounded-full bg-blue-600/15 blur-[110px]" />
      </div>

      <div className="container-x grid items-center gap-14 lg:grid-cols-2 lg:gap-10">
        <motion.div variants={container} initial="hidden" animate="visible" className="order-2 lg:order-1">
          <motion.div variants={item} className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.06] px-3.5 py-1.5 text-xs font-medium text-emerald-300">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-emerald-400" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            Available for internships & full-stack roles
          </motion.div>

          <motion.h1 variants={item} className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl xl:text-6xl">
            MUTHUKARUPPAN{" "}
            <span className="text-gradient">V</span>
          </motion.h1>

          <motion.p variants={item} className="mt-4 font-mono text-base text-slate-300 sm:text-lg">
            {PROFILE.designation} · <span className="text-cyan-300">{PROFILE.role}</span>
          </motion.p>

          <motion.h2 variants={item} className="mt-6 max-w-xl text-2xl font-bold leading-snug text-white sm:text-3xl">
            {PROFILE.tagline}
          </motion.h2>

          <motion.p variants={item} className="mt-4 max-w-xl text-slate-400">
            {PROFILE.intro}
          </motion.p>

          <motion.div variants={item} className="mt-5 flex flex-wrap items-center gap-3 text-sm text-slate-400">
            <span className="inline-flex items-center gap-1.5">
              <MapPin className="h-4 w-4 text-cyan-400" />
              {PROFILE.location}
            </span>
            <span className="hidden h-1 w-1 rounded-full bg-slate-600 sm:block" />
            <span className="font-mono text-xs text-slate-500">// open to remote & on-site</span>
          </motion.div>

          <motion.div variants={item} className="mt-8 flex flex-wrap items-center gap-3 sm:gap-4">
            <a
              href="#projects"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3.5 text-sm font-semibold text-white shadow-glow transition-all hover:-translate-y-0.5 hover:brightness-110"
            >
              View My Projects
              <ArrowRight className="h-4 w-4" />
            </a>
            <a
              href={resumeHref.href}
              target={PROFILE.resumeUrl ? "_blank" : undefined}
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-6 py-3.5 text-sm font-semibold text-slate-200 backdrop-blur transition-all hover:-translate-y-0.5 hover:border-cyan-400/40 hover:text-cyan-300"
            >
              <Download className="h-4 w-4" />
              Download Resume
            </a>
          </motion.div>

          <motion.div variants={item} className="mt-7 flex items-center gap-3">
            <span className="text-xs font-medium tracking-widest text-slate-500 uppercase">
              Find me on
            </span>
            <div className="flex gap-3">
              <SocialLink href={PROFILE.linkedin} label="LinkedIn" icon={Linkedin} />
              <SocialLink href={PROFILE.github} label="GitHub" icon={Github} />
              <SocialLink href={`mailto:${PROFILE.email}`} label="Email" icon={Mail} />
            </div>
          </motion.div>
        </motion.div>

        <div className="order-1 lg:order-2">
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut", delay: 0.2 }}
          >
            <CodeWindow />

            <div className="mt-12 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {PROFILE.heroStats.map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-xl border border-white/[0.06] bg-surface/60 px-4 py-3 text-center backdrop-blur"
                >
                  <div className="text-xl font-bold text-white sm:text-2xl">{stat.value}</div>
                  <div className="mt-0.5 text-[11px] text-slate-500 sm:text-xs">{stat.label}</div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}