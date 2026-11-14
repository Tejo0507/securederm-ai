"use client";

import { useEffect, useState, type RefObject } from "react";

/**
 * Whether an element's content is cut off by a line clamp (or any fixed
 * height). Re-checked whenever the element resizes, so a description that
 * fits on a wide screen but not on a phone gets its toggle only where needed.
 *
 * Pass `active: false` while the content is expanded: there is nothing
 * clamped to measure then, and the last answer is kept.
 */
export function useOverflows(ref: RefObject<HTMLElement>, active = true): boolean {
  const [overflows, setOverflows] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || !active) return;
    const measure = () => setOverflows(el.scrollHeight > el.clientHeight + 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, active]);

  return overflows;
}
