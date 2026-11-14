"use client";

import { useEffect } from "react";

/**
 * Keep the tab title at `title` while the component is mounted.
 *
 * Setting document.title once from an effect loses a race on first load:
 * Next applies the route's metadata <title> after mount effects have run.
 * Watching <head> and putting the title back whenever something else
 * changes it makes the result independent of that ordering.
 */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    // On a client-side navigation away, Next writes the next route's title
    // before this component unmounts. Only defend the title while the URL is
    // still the page it belongs to, or it would win that race too.
    const path = window.location.pathname;
    const apply = () => {
      if (window.location.pathname !== path) return;
      if (document.title !== title) document.title = title;
    };
    apply();
    const observer = new MutationObserver(apply);
    observer.observe(document.head, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [title]);
}
