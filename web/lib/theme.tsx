"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { THEME_STORAGE_KEY, type ResolvedTheme, type ThemePreference } from "@/lib/themeScript";

export type { ResolvedTheme, ThemePreference } from "@/lib/themeScript";

interface ThemeState {
  /** What the visitor chose; null until read on the client (server and first render). */
  preference: ThemePreference | null;
  /** What is actually shown. */
  resolved: ResolvedTheme;
  setPreference: (next: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

/** Browser chrome color for each theme (matches --canvas). */
const CHROME: Record<ResolvedTheme, string> = { light: "#f5f4f0", dark: "#0d0f0e" };

function parsePreference(value: string | null | undefined): ThemePreference {
  return value === "light" || value === "dark" ? value : "system";
}

/**
 * Owns the color theme after first paint (the inline script in app/layout.tsx
 * handles the paint itself): applies changes to <html>, follows the OS while
 * the preference is "system", remembers the choice, and keeps other open
 * tabs in step.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference | null>(null);
  const [resolved, setResolved] = useState<ResolvedTheme>("light");

  // Start from what the inline script already applied.
  useEffect(() => {
    setPreferenceState(parsePreference(document.documentElement.dataset.themePref));
  }, []);

  useEffect(() => {
    if (preference === null) return;
    const root = document.documentElement;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const next: ResolvedTheme = preference === "system" ? (media.matches ? "dark" : "light") : preference;
      root.dataset.theme = next;
      root.dataset.themePref = preference;
      setResolved(next);
      // Both theme-color metas carry media queries for the OS scheme; point
      // them at the theme actually shown so the browser chrome matches.
      document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.setAttribute("content", CHROME[next]));
    };
    apply();
    if (preference !== "system") return;
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preference]);

  // A choice made in another tab applies here too.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === THEME_STORAGE_KEY || e.key === null) setPreferenceState(parsePreference(e.newValue));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    try {
      if (next === "system") localStorage.removeItem(THEME_STORAGE_KEY);
      else localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Storage blocked: the choice still applies for this page view.
    }
  }, []);

  return <ThemeContext.Provider value={{ preference, resolved, setPreference }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside <ThemeProvider>");
  return value;
}
