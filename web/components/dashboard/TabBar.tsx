"use client";

import { KeyboardEvent, useEffect, useRef } from "react";
import { motion } from "framer-motion";

export interface TabDef<K extends string> {
  key: K;
  label: string;
}

/** DOM ids shared with the panel so assistive tech can link a tab to its content. */
export const tabId = (key: string) => `tab-${key}`;
export const panelId = (key: string) => `panel-${key}`;

/**
 * The dashboard's tab strip. It scrolls sideways on narrow screens instead of
 * pushing the whole page wider, keeps the active tab in view, and follows the
 * ARIA tabs pattern: arrow keys, Home and End move between tabs.
 */
export default function TabBar<K extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef<K>[];
  active: K;
  onChange: (key: K) => void;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  // On a phone the active tab can sit off-screen (after a deep link, or after
  // "Diagnose Wound" on the overview): bring it into view.
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`#${tabId(active)}`);
    el?.scrollIntoView?.({ inline: "center", block: "nearest" });
  }, [active]);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex((t) => t.key === active);
    let next = index;
    if (e.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    onChange(tabs[next].key);
    listRef.current?.querySelector<HTMLElement>(`#${tabId(tabs[next].key)}`)?.focus();
  }

  return (
    <div className="border-b border-white/5">
      <div
        ref={listRef}
        role="tablist"
        aria-label="Dashboard sections"
        onKeyDown={onKeyDown}
        className="max-w-7xl mx-auto px-6 flex gap-1 overflow-x-auto no-scrollbar"
      >
        {tabs.map((t) => {
          const selected = t.key === active;
          return (
            <button
              key={t.key}
              id={tabId(t.key)}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls={panelId(t.key)}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(t.key)}
              className={`shrink-0 whitespace-nowrap px-4 py-3 text-sm font-medium transition-colors relative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/70 focus-visible:ring-inset rounded-t ${
                selected ? "text-white" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {t.label}
              {selected && (
                <motion.div
                  layoutId="tab-indicator"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500"
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
