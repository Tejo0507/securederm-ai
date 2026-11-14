"use client";

import { useRef, type KeyboardEvent } from "react";
import { useTheme, type ThemePreference } from "@/lib/theme";
import { IconMonitor, IconMoon, IconSun } from "@/components/ui/icons";

const OPTIONS: { value: ThemePreference; label: string; icon: React.ReactNode }[] = [
  { value: "system", label: "Match system", icon: <IconMonitor size={15} /> },
  { value: "light", label: "Light", icon: <IconSun size={15} /> },
  { value: "dark", label: "Dark", icon: <IconMoon size={15} /> },
];

/**
 * Three-way theme choice: a recessed track with the selected option raised
 * like a key. A radio group, so arrow keys move the choice and Tab moves on.
 * `showLabels` spells the options out (the phone menu); otherwise icons only.
 */
export default function ThemeSwitch({ showLabels = false, className = "" }: { showLabels?: boolean; className?: string }) {
  const { preference, setPreference } = useTheme();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  // Until the client has read the stored choice, show "system" without
  // committing to it (preference is null on the server and first render).
  const current = preference ?? "system";

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const index = OPTIONS.findIndex((o) => o.value === current);
    const next = (index + step + OPTIONS.length) % OPTIONS.length;
    setPreference(OPTIONS[next].value);
    buttons.current[next]?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label="Color theme"
      onKeyDown={onKeyDown}
      className={`inline-flex items-center gap-0.5 rounded-md border border-line bg-sunken p-0.5 shadow-[inset_0_1px_2px_rgb(var(--shadow)/0.08)] ${className}`}
    >
      {OPTIONS.map((o, i) => {
        const selected = current === o.value;
        return (
          <button
            key={o.value}
            ref={(el) => {
              buttons.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={showLabels ? undefined : o.label}
            title={showLabels ? undefined : o.label}
            tabIndex={selected ? 0 : -1}
            onClick={() => setPreference(o.value)}
            className={`inline-flex h-7 items-center justify-center gap-1.5 rounded-[5px] text-[13px] transition-[background-color,color,box-shadow,transform] duration-150 ${
              showLabels ? "flex-1 px-2.5" : "w-7"
            } ${
              selected
                ? "bg-surface text-ink shadow-[0_2px_0_rgb(var(--line-strong)),0_1px_3px_rgb(var(--shadow)/0.1)]"
                : "text-ink-3 hover:text-ink active:translate-y-px"
            }`}
          >
            {o.icon}
            {showLabels && <span>{o.value === "system" ? "System" : o.label}</span>}
          </button>
        );
      })}
    </div>
  );
}
