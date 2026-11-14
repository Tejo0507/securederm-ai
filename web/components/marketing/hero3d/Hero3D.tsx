"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { useCan3D } from "@/lib/useCan3D";
import { useThemeColors } from "@/lib/useThemeColors";
import HeroGraph from "@/components/marketing/HeroGraph";
import Badge from "@/components/ui/Badge";
import { IconPause, IconPlay } from "@/components/ui/icons";
import type { ScenePhase } from "./FederationScene";

// three.js is a large library; keep it out of the page's first load entirely.
const FederationScene = dynamic(() => import("./FederationScene"), { ssr: false });

export const ROUND_PHASES: { phase: ScenePhase; label: string; detail: string }[] = [
  { phase: "training", label: "Train", detail: "Each hospital trains on its own images." },
  { phase: "uploading", label: "Send", detail: "Clipped, noised weight updates travel to the hub." },
  { phase: "aggregating", label: "Average", detail: "FedAvg merges every update into one model." },
  { phase: "distributing", label: "Return", detail: "The improved model returns to every site." },
];

const PHASE_MS = 2800;
const FIRST_ROUND = 14;

/** The hero's federation scene with its round controls, or the 2D graph where 3D is unavailable. */
export default function Hero3D() {
  const can3D = useCan3D();
  const colors = useThemeColors();
  const stage = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  const [playing, setPlaying] = useState(true);
  const [tick, setTick] = useState(0);
  const [finePointer, setFinePointer] = useState(false);
  const step = tick % ROUND_PHASES.length;
  const round = FIRST_ROUND + Math.floor(tick / ROUND_PHASES.length);
  const current = ROUND_PHASES[step];

  useEffect(() => setFinePointer(window.matchMedia("(hover: hover) and (pointer: fine)").matches), []);

  // Stop rendering (and the round clock) while the hero is scrolled away.
  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.05 });
    io.observe(el);
    return () => io.disconnect();
  }, [can3D]);

  const running = !!can3D && visible && playing;
  useEffect(() => {
    if (!running) return;
    const id = window.setTimeout(() => setTick((t) => t + 1), PHASE_MS);
    return () => window.clearTimeout(id);
  }, [running, tick]);

  if (can3D === false) return <HeroGraph />;

  const jumpTo = (i: number) => {
    setTick((t) => t - (t % ROUND_PHASES.length) + i);
    setPlaying(false);
  };

  return (
    <figure
      ref={stage}
      className="relative aspect-[4/5] w-full overflow-hidden rounded-xl sm:aspect-[6/5] lg:aspect-square"
    >
      {/* A soft pool of light under the model. */}
      <div
        aria-hidden="true"
        className="absolute inset-x-[8%] bottom-[6%] top-[22%] rounded-[50%] bg-[radial-gradient(closest-side,rgb(var(--accent)/0.12),transparent)]"
      />
      {can3D && colors ? (
        <FederationScene colors={colors} phase={current.phase} active={visible} round={round} />
      ) : (
        <div aria-hidden="true" className="absolute inset-[18%] animate-pulse rounded-full bg-sunken/60" />
      )}

      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between gap-3 p-3 sm:p-4">
        <Badge tone="accent" dot pulse={running}>
          Live simulation
        </Badge>
        {finePointer && <span className="font-mono text-2xs text-ink-3">drag to rotate</span>}
      </div>

      <figcaption className="absolute inset-x-0 bottom-0 p-3 sm:p-4">
        <div className="rounded-lg border border-line bg-surface/85 p-2.5 shadow-float backdrop-blur-md sm:p-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? "Pause the round" : "Play the round"}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-line bg-canvas text-ink transition-colors hover:border-ink-3"
            >
              {playing ? <IconPause size={14} /> : <IconPlay size={14} />}
            </button>
            <ol className="grid flex-1 grid-cols-4 gap-1.5" aria-label={`Round ${round} phases`}>
              {ROUND_PHASES.map((p, i) => {
                const done = i < step;
                const now = i === step;
                return (
                  <li key={p.phase}>
                    <button
                      type="button"
                      onClick={() => jumpTo(i)}
                      aria-current={now ? "step" : undefined}
                      className="group w-full rounded px-1 pb-1 pt-1.5 text-left"
                    >
                      <span className="block h-1 overflow-hidden rounded-full bg-sunken">
                        <span
                          key={now ? tick : undefined}
                          className={`block h-full origin-left rounded-full bg-accent ${
                            done ? "scale-x-100" : now ? (running ? "animate-grow-x" : "scale-x-100") : "scale-x-0"
                          }`}
                          style={now && running ? { animationDuration: `${PHASE_MS}ms` } : undefined}
                        />
                      </span>
                      <span
                        className={`mt-1.5 block truncate font-mono text-2xs ${
                          now ? "text-ink" : "text-ink-3 group-hover:text-ink-2"
                        }`}
                      >
                        <span className="hidden sm:inline">{String(i + 1).padStart(2, "0")} </span>
                        {p.label}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>
          {/* Announced only when the visitor is stepping through; autoplay would chatter. */}
          <p className="mt-1.5 px-1 text-[13px] text-ink-2 sm:truncate" aria-live={playing ? "off" : "polite"}>
            <span className="font-medium text-ink">Round {round}.</span> {current.detail}
          </p>
        </div>
      </figcaption>
    </figure>
  );
}
