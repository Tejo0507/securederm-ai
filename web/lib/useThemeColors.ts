"use client";

import { useEffect, useState } from "react";

/** Design tokens a canvas needs, as "#rrggbb" strings (see globals.css). */
export interface ThemeColors {
  canvas: string;
  surface: string;
  sunken: string;
  line: string;
  lineStrong: string;
  ink: string;
  ink2: string;
  ink3: string;
  accent: string;
  accentSoft: string;
  onAccent: string;
  warn: string;
  dark: boolean;
}

const TOKENS: Record<Exclude<keyof ThemeColors, "dark">, string> = {
  canvas: "--canvas",
  surface: "--surface",
  sunken: "--sunken",
  line: "--line",
  lineStrong: "--line-strong",
  ink: "--ink",
  ink2: "--ink-2",
  ink3: "--ink-3",
  accent: "--accent",
  accentSoft: "--accent-soft",
  onAccent: "--on-accent",
  warn: "--warn",
};

/** "14 107 82" (the token format) to "#0e6b52". */
function channelsToHex(value: string): string {
  const parts = value.trim().split(/\s+/).map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return "#888888";
  return `#${parts.map((n) => Math.round(n).toString(16).padStart(2, "0")).join("")}`;
}

export function readThemeColors(): ThemeColors {
  const style = getComputedStyle(document.documentElement);
  const colors = Object.fromEntries(
    Object.entries(TOKENS).map(([key, prop]) => [key, channelsToHex(style.getPropertyValue(prop))]),
  ) as Omit<ThemeColors, "dark">;
  return { ...colors, dark: style.colorScheme.includes("dark") };
}

/**
 * The current theme's colors for things CSS can't style (WebGL, canvas).
 * Re-reads when the OS scheme flips or the root element's theme attributes
 * change, so a scene recolors along with the rest of the page.
 */
export function useThemeColors(): ThemeColors | null {
  const [colors, setColors] = useState<ThemeColors | null>(null);

  useEffect(() => {
    const update = () => setColors(readThemeColors());
    update();
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", update);
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme", "style"] });
    return () => {
      media.removeEventListener("change", update);
      observer.disconnect();
    };
  }, []);

  return colors;
}
