import Reveal from "./Reveal";

export default function SectionHeading({ index, eyebrow, title, subtitle, align = "center" }) {
  const alignment =
    align === "left"
      ? "text-left items-start"
      : "text-center items-center";

  return (
    <Reveal className={`flex flex-col gap-3 ${alignment} mb-12 sm:mb-16`}>
      {(eyebrow || index) && (
        <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 font-mono text-xs tracking-widest text-cyan-300 uppercase">
          {index && <span className="text-slate-500">{index}</span>}
          {eyebrow}
        </span>
      )}
      <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl lg:text-5xl">
        {title}
      </h2>
      {subtitle && <p className="max-w-2xl text-base text-slate-400 sm:text-lg">{subtitle}</p>}
      <span className="h-1 w-16 rounded-full bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500" />
    </Reveal>
  );
}