"use client";

import { KeyboardEvent, ReactNode, useEffect, useRef } from "react";

export interface TabDef<K extends string> {
  key: K;
  label: string;
  icon?: ReactNode;
}

/** DOM ids shared with the panel so assistive tech can link a tab to its content. */
export const tabId = (key: string) => `tab-${key}`;
export const panelId = (key: string) => `panel-${key}`;

/**
 * The dashboard's section navigation. A vertical sidebar list on wide screens
 * and a sideways-scrolling strip on narrow ones (it never pushes the page
 * wider). Follows the ARIA tabs pattern: arrow keys, Home and End move between
 * tabs in either orientation.
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
  // a quick action on the overview): bring it into view.
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`#${tabId(active)}`);
    el?.scrollIntoView?.({ inline: "center", block: "nearest" });
  }, [active]);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex((t) => t.key === active);
    let next = index;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (index + 1) % tabs.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (index - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    onChange(tabs[next].key);
    listRef.current?.querySelector<HTMLElement>(`#${tabId(tabs[next].key)}`)?.focus();
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label="Dashboard sections"
      onKeyDown={onKeyDown}
      className="no-scrollbar flex gap-1 overflow-x-auto px-3 sm:px-4 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:px-0"
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
            className={`group relative flex shrink-0 items-center gap-2.5 whitespace-nowrap px-3 py-3 text-sm font-medium transition-colors duration-150 focus-visible:outline-offset-[-2px] lg:h-9 lg:rounded lg:py-0 ${
              selected
                ? "text-ink after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-accent lg:bg-surface lg:shadow-edge-neutral lg:ring-1 lg:ring-line lg:after:hidden"
                : "text-ink-2 hover:text-ink lg:hover:bg-ink/[0.05]"
            }`}
          >
            {t.icon && (
              <span
                className={`hidden transition-colors lg:inline-flex ${selected ? "text-accent" : "text-ink-3 group-hover:text-ink-2"}`}
              >
                {t.icon}
              </span>
            )}
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
