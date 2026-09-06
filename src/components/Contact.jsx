import { useState } from "react";
import { CheckCircle2, Github, Linkedin, Loader2, Mail, Send } from "lucide-react";
import { PROFILE } from "../data/config";
import Reveal from "./common/Reveal";
import SectionHeading from "./common/SectionHeading";

// ---------------------------------------------------------------------
// CONTACT FORM SETUP
// The form currently opens the visitor's email app (mailto) — no backend.
// To wire it to Google Sheets + Apps Script (mailto -> Google Sheets):
//   1. Follow google-sheets-apps-script.gs at the project root (deploy a Web app).
//   2. Paste the Web app URL below instead of "".
//   3. handleSubmit will POST the message and save it to your sheet.
// Always keep a mailto fallback so the form works even without the endpoint.
// ---------------------------------------------------------------------
const CONTACT_ENDPOINT =
  "https://script.google.com/macros/s/AKfycbw4-UTjrosfswlE8zXoBhi2glo1rj3TJL_HQ89RjouJCfIGDIunO98Ld-MYlMVPWMjyvw/exec";

const CONTACT_CARDS = [
  {
    label: "Email",
    value: PROFILE.email,
    href: `mailto:${PROFILE.email}`,
    icon: Mail,
    accent: "border-cyan-400/25 bg-cyan-400/[0.06] text-cyan-300",
  },
  {
    label: "LinkedIn",
    value: "in/muthukaruppanv",
    href: PROFILE.linkedin,
    icon: Linkedin,
    accent: "border-blue-400/25 bg-blue-400/[0.06] text-blue-300",
  },
  {
    label: "GitHub",
    value: "muthukaruppanV07",
    href: PROFILE.github,
    icon: Github,
    accent: "border-purple-400/25 bg-purple-400/[0.06] text-purple-300",
  },
];

const inputClasses =
  "w-full rounded-xl border border-white/10 bg-card/80 px-4 py-3 text-sm text-white placeholder:text-slate-500 outline-none transition-all focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/20";

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [status, setStatus] = useState("idle"); // "idle" | "sending" | "sent" | "error"

  const handleChange = (e) =>
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim() || !form.message.trim()) {
      setStatus("error");
      return;
    }

    const subject = encodeURIComponent(`Portfolio contact from ${form.name}`);
    const body = encodeURIComponent(
      `Name: ${form.name}\nEmail: ${form.email}\n\n${form.message}`,
    );

    setStatus("sending");

    try {
      if (CONTACT_ENDPOINT) {
        const res = await fetch(CONTACT_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "text/plain;charset=utf-8" },
          body: JSON.stringify(form),
        });
        const result = await res.json().catch(() => ({}));
        if (!res.ok || result.ok === false) throw new Error("Request failed");
      } else {
        window.location.href = `mailto:${PROFILE.email}?subject=${subject}&body=${body}`;
        setStatus("sent");
        setForm({ name: "", email: "", message: "" });
        return;
      }
      setStatus("sent");
      setForm({ name: "", email: "", message: "" });
    } catch (err) {
      setStatus("error");
    }
  };

  return (
    <section id="contact" className="section-pad relative overflow-hidden">
      <div aria-hidden="true" className="absolute inset-0 -z-10">
        <div className="absolute bottom-0 left-1/2 h-72 w-[36rem] max-w-full -translate-x-1/2 rounded-full bg-cyan-500/10 blur-[120px]" />
      </div>

      <div className="container-x">
        <SectionHeading
          index="10"
          eyebrow="Contact"
          title="Let's build something together"
          subtitle="I am actively looking for opportunities to learn, contribute and grow through software development internships and real-world projects."
        />

        <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-5">
          <Reveal className="lg:col-span-2">
            <div className="space-y-4">
              {CONTACT_CARDS.map((card) => {
                const Icon = card.icon;
                return (
                  <a
                    key={card.label}
                    href={card.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center gap-4 rounded-2xl border border-white/[0.08] bg-card/80 p-4 transition-all duration-300 hover:-translate-y-1 hover:border-white/20 hover:shadow-glow-soft"
                  >
                    <span className={`flex h-11 w-11 items-center justify-center rounded-xl border ${card.accent}`}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <span>
                      <span className="block text-xs text-slate-500">{card.label}</span>
                      <span className="block text-sm font-medium break-all text-slate-200 group-hover:text-white">
                        {card.value}
                      </span>
                    </span>
                  </a>
                );
              })}
            </div>

            <p className="mt-6 text-sm leading-relaxed text-slate-500">
              Prefer a direct message? Email me at{" "}
              <a href={`mailto:${PROFILE.email}`} className="font-medium text-cyan-300 hover:underline">
                {PROFILE.email}
              </a>{" "}
              — I usually reply within 24 hours.
            </p>
          </Reveal>

          <Reveal delay={1} className="lg:col-span-3">
            <form
              onSubmit={handleSubmit}
              className="rounded-3xl border border-white/[0.08] bg-card/80 p-6 backdrop-blur sm:p-8"
            >
              <h3 className="text-lg font-bold text-white">Send me a message</h3>
              <p className="mt-1 text-sm text-slate-500">
                Fill in the form and it will open your email app, ready to send.
              </p>

              <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-xs font-medium text-slate-300">Name</span>
                  <input
                    type="text"
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    placeholder="Your name"
                    required
                    className={inputClasses}
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-xs font-medium text-slate-300">Email</span>
                  <input
                    type="email"
                    name="email"
                    value={form.email}
                    onChange={handleChange}
                    placeholder="you@example.com"
                    required
                    className={inputClasses}
                  />
                </label>
              </div>

              <label className="mt-5 block">
                <span className="mb-2 block text-xs font-medium text-slate-300">Message</span>
                <textarea
                  name="message"
                  value={form.message}
                  onChange={handleChange}
                  rows="5"
                  placeholder="Tell me about an internship, project or opportunity…"
                  required
                  className={`${inputClasses} resize-none`}
                />
              </label>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
                <button
                  type="submit"
                  disabled={status === "sending"}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-7 py-3.5 text-sm font-semibold text-white shadow-glow transition-all hover:-translate-y-0.5 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {status === "sending" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Sending…
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4" />
                      Send Message
                    </>
                  )}
                </button>

                {status === "sent" && (
                  <span className="inline-flex items-center gap-2 text-sm font-medium text-emerald-300">
                    <CheckCircle2 className="h-4 w-4" />
                    {CONTACT_ENDPOINT ? "Message sent" : "Opening your email app…"}
                  </span>
                )}
                {status === "error" && (
                  <span className="text-sm font-medium text-rose-300">
                    Please fill in all the fields.
                  </span>
                )}
              </div>
            </form>
          </Reveal>
        </div>
      </div>
    </section>
  );
}