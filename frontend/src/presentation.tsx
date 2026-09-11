import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';

interface PresentationState {
  enabled: boolean;
  enter: () => void;
  exit: () => void;
}

const Ctx = createContext<PresentationState>({ enabled: false, enter: () => undefined, exit: () => undefined });

const KEY = 'skyguard-presentation';

export function PresentationProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState(() => {
    try {
      return localStorage.getItem(KEY) === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    document.documentElement.classList.toggle('presentation-mode', enabled);
    try {
      localStorage.setItem(KEY, enabled ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [enabled]);

  const enter = useCallback(() => {
    setEnabled(true);
    window.scrollTo({ top: 0 });
  }, []);
  const exit = useCallback(() => setEnabled(false), []);

  return <Ctx.Provider value={{ enabled, enter, exit }}>{children}</Ctx.Provider>;
}

export const usePresentation = () => useContext(Ctx);
