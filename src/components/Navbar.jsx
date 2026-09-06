import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileText, Menu, X } from "lucide-react";
import { NAV_LINKS, PROFILE } from "../data/config";
import { useActiveSection } from "../hooks/useActiveSection";
import cn from "../lib/cn";

function NavLink({ href, label, active, onNavigate }) {
  return (
    <a
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active ? "text-cyan-300" : "text-slate-300 hover:text-white",
      )}
    >
      {label}
      {active && (
        <motion.span
          layoutId="nav-underline"
          className="absolute inset-x-3 -bottom-0.5 h-px bg-gradient-to-r from-cyan-400 to-purple-400"
        />
      )}
    </a>
  );
}

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const active = useActiveSection(NAV_LINKS);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const onResize = () => window.innerWidth >= 768 && setOpen(false);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const resumeHref = PROFILE.resumeUrl || "#contact";

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled
          ? "border-b border-white/[0.06] bg-base/70 backdrop-blur-xl"
          : "bg-transparent",
      )}
    >
      <nav className="container-x flex h-16 items-center justify-between gap-4">
        <a href="#home" className="group flex items-center gap-2" aria-label="Go to home">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-purple-500 font-mono text-sm font-bold text-base shadow-glow">
            MV
          </span>
          <span className="hidden text-sm font-bold tracking-wide text-white sm:block">
            MUTHUKARUPPAN <span className="text-cyan-400">V</span>
          </span>
        </a>

        <ul className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <li key={link.href}>
              <NavLink
                href={link.href}
                label={link.label}
                active={active === link.href}
              />
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-2">
          <a
            href={resumeHref}
            className="hidden items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-glow transition-all hover:brightness-110 hover:shadow-lg sm:inline-flex"
          >
            <FileText className="h-4 w-4" />
            View Resume
          </a>
          <button
            type="button"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 text-slate-200 transition-colors hover:bg-white/5 md:hidden"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden border-b border-white/[0.06] bg-base/95 backdrop-blur-xl md:hidden"
          >
            <ul className="container-x flex flex-col gap-1 py-4">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "block rounded-lg px-3 py-3 text-base font-medium transition-colors",
                      active === link.href
                        ? "bg-white/[0.06] text-cyan-300"
                        : "text-slate-200 hover:bg-white/[0.04]",
                    )}
                  >
                    {link.label}
                  </a>
                </li>
              ))}
              <li className="mt-2">
                <a
                  href={resumeHref}
                  onClick={() => setOpen(false)}
                  className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-3 text-sm font-semibold text-white"
                >
                  <FileText className="h-4 w-4" />
                  View Resume
                </a>
              </li>
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}