import { useEffect, useState } from "react";

/**
 * Tracks which section is currently in view (by nav anchor hash).
 * Returns the active href (e.g. "#home") or "" when none matched.
 */
export function useActiveSection(links) {
  const [active, setActive] = useState("");

  useEffect(() => {
    const onScroll = () => {
      let current = "";
      for (const link of links) {
        const el = document.querySelector(link.href);
        if (!el) continue;
        if (el.getBoundingClientRect().top <= 160) {
          current = link.href;
        }
      }
      setActive(current);
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [links]);

  return active;
}