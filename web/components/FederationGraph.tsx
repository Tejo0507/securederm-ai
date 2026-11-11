"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { IconHospital, IconLock, IconMerge } from "@/components/ui/icons";

export type FedPhase = "idle" | "training" | "uploading" | "aggregating" | "distributing";

export const FED_NODES = [
  { id: "A", label: "Hospital A", x: 0.17, y: 0.2 },
  { id: "B", label: "Hospital B", x: 0.17, y: 0.8 },
  { id: "C", label: "Hospital C", x: 0.83, y: 0.2 },
  { id: "D", label: "Hospital D", x: 0.83, y: 0.8 },
] as const;

const CENTER = { x: 0.5, y: 0.5 };

/**
 * Four hospitals around one aggregator. Nodes are HTML (so text stays readable
 * at any width); edges are an SVG drawn in pixels from the measured size, so
 * dashes and packets keep their proportions on phones and desktops alike.
 */
export default function FederationGraph({
  phase,
  round,
  className = "",
}: {
  phase: FedPhase;
  round?: number;
  className?: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const reduce = useReducedMotion();

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ w: width, h: height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const moving = phase === "uploading" || phase === "distributing";
  const toCenter = phase === "uploading";
  const training = phase === "training";
  const aggregating = phase === "aggregating";

  return (
    <div ref={box} className={`relative ${className}`}>
      {size.w > 0 && (
        <svg width={size.w} height={size.h} className="absolute inset-0" aria-hidden="true">
          {FED_NODES.map((n, i) => {
            const x1 = n.x * size.w;
            const y1 = n.y * size.h;
            const x2 = CENTER.x * size.w;
            const y2 = CENTER.y * size.h;
            // An elbow path reads as "wiring", not a starburst.
            const midX = (x1 + x2) / 2;
            const d = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
            return (
              <g key={n.id}>
                <path
                  d={d}
                  fill="none"
                  stroke="rgb(var(--line-strong))"
                  strokeWidth={1.25}
                />
                <path
                  d={d}
                  fill="none"
                  stroke="rgb(var(--accent))"
                  strokeWidth={1.75}
                  strokeDasharray="3 7"
                  className={moving ? (toCenter ? "fed-flow-in" : "fed-flow-out") : ""}
                  style={{ opacity: moving ? 1 : 0, transition: "opacity 300ms" }}
                />
                {moving && !reduce && (
                  <motion.circle
                    key={`${phase}-${n.id}`}
                    r={4}
                    fill="rgb(var(--accent))"
                    stroke="rgb(var(--surface))"
                    strokeWidth={2}
                    initial={toCenter ? { cx: x1, cy: y1 } : { cx: x2, cy: y2 }}
                    animate={toCenter ? { cx: x2, cy: y2 } : { cx: x1, cy: y1 }}
                    transition={{
                      duration: 1.1,
                      ease: [0.45, 0, 0.55, 1],
                      repeat: Infinity,
                      repeatDelay: 0.2,
                      delay: i * 0.12,
                    }}
                  />
                )}
              </g>
            );
          })}
        </svg>
      )}

      {/* aggregator */}
      <div
        className="absolute -translate-x-1/2 -translate-y-1/2"
        style={{ left: `${CENTER.x * 100}%`, top: `${CENTER.y * 100}%` }}
      >
        <div
          className={`relative flex w-[132px] flex-col items-center rounded-lg border px-3 py-3 text-center transition-[border-color,background-color,box-shadow] duration-300 sm:w-[156px] ${
            aggregating
              ? "border-accent bg-accent text-accent-on shadow-float"
              : "border-ink/80 bg-ink text-canvas shadow-raise"
          }`}
        >
          <IconMerge size={18} />
          <span className="mt-1.5 text-[13px] font-semibold">Aggregator</span>
          <span className="font-mono text-2xs opacity-70">
            {round ? `FedAvg · R${round}` : "FedAvg"}
          </span>
          {aggregating && !reduce && (
            <span className="absolute inset-0 -z-10 animate-ping rounded-lg bg-accent/40" />
          )}
        </div>
      </div>

      {/* hospitals */}
      {FED_NODES.map((n) => (
        <div
          key={n.id}
          className="absolute -translate-x-1/2 -translate-y-1/2"
          style={{ left: `${n.x * 100}%`, top: `${n.y * 100}%` }}
        >
          <div
            className={`w-[104px] rounded-lg border bg-surface px-2.5 py-2 transition-[border-color,box-shadow] duration-300 sm:w-[136px] sm:px-3 ${
              training ? "border-accent shadow-[0_0_0_4px_rgb(var(--accent)/0.12)]" : "border-line-strong shadow-raise"
            }`}
          >
            <div className="flex items-center gap-1.5 text-ink">
              <IconHospital size={14} className={training ? "text-accent" : "text-ink-3"} />
              <span className="truncate text-xs font-semibold sm:text-[13px]">{n.label}</span>
            </div>
            <div className="mt-1 flex items-center gap-1 text-2xs text-ink-3">
              <IconLock size={11} />
              <span className="truncate">{training ? "training" : "data on site"}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
