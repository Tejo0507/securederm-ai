"use client";

import { useEffect, useRef, type ElementType, type ReactNode } from "react";

/**
 * A card that turns a few degrees toward the pointer, with a soft glare
 * where the light would catch it. Children marked `lift-1` / `lift-2` (see
 * globals.css) float above the face at different depths.
 *
 * Mouse and pen only, and never under prefers-reduced-motion: on touch it
 * is a plain card. Pointer moves write CSS variables directly (one write per
 * animation frame) instead of going through React state.
 */
export default function Tilt({
  children,
  className = "",
  max = 7,
  glare = true,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  /** Largest rotation in degrees. */
  max?: number;
  glare?: boolean;
  as?: ElementType;
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const allowed = window.matchMedia("(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)");
    if (!allowed.matches) return;

    let frame = 0;
    let px = 0.5;
    let py = 0.5;
    const paint = () => {
      frame = 0;
      el.style.setProperty("--tilt-x", `${((0.5 - py) * max * 2).toFixed(2)}deg`);
      el.style.setProperty("--tilt-y", `${((px - 0.5) * max * 2).toFixed(2)}deg`);
      el.style.setProperty("--glare-x", `${(px * 100).toFixed(1)}%`);
      el.style.setProperty("--glare-y", `${(py * 100).toFixed(1)}%`);
    };
    const onMove = (e: PointerEvent) => {
      if (e.pointerType === "touch") return;
      const rect = el.getBoundingClientRect();
      px = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
      py = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height));
      el.dataset.tilting = "true";
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const onLeave = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      delete el.dataset.tilting;
      el.style.setProperty("--tilt-x", "0deg");
      el.style.setProperty("--tilt-y", "0deg");
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerleave", onLeave);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerleave", onLeave);
    };
  }, [max]);

  return (
    <Tag
      ref={ref}
      className={`tilt group/tilt relative [transform-style:preserve-3d] ${className}`}
    >
      {children}
      {glare && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-300 [background:radial-gradient(circle_at_var(--glare-x,50%)_var(--glare-y,0%),rgb(255_255_255/0.22),transparent_55%)] group-data-[tilting=true]/tilt:opacity-100 dark:[background:radial-gradient(circle_at_var(--glare-x,50%)_var(--glare-y,0%),rgb(255_255_255/0.06),transparent_55%)]"
        />
      )}
    </Tag>
  );
}
