"use client";

import { useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";
import FederationGraph, { type FedPhase } from "@/components/FederationGraph";
import Badge from "@/components/ui/Badge";

const CYCLE: { phase: FedPhase; label: string }[] = [
  { phase: "training", label: "Training on local images" },
  { phase: "uploading", label: "Sending noised weight updates" },
  { phase: "aggregating", label: "Averaging updates (FedAvg)" },
  { phase: "distributing", label: "Returning the improved model" },
];

/** The hero illustration: the federation graph stepping through one round on a loop. */
export default function HeroGraph() {
  const reduce = useReducedMotion();
  const [tick, setTick] = useState(0);
  const step = tick % CYCLE.length;
  const round = 14 + Math.floor(tick / CYCLE.length);

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 2400);
    return () => window.clearInterval(id);
  }, [reduce]);

  const current = reduce ? { phase: "idle" as FedPhase, label: "One federated round" } : CYCLE[step];

  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-surface shadow-float">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-line-strong" />
          <span className="h-2 w-2 rounded-full bg-line-strong" />
          <span className="h-2 w-2 rounded-full bg-line-strong" />
          <span className="ml-2 font-mono text-2xs text-ink-3">network / round {round}</span>
        </div>
        <Badge tone="accent" dot pulse={!reduce}>
          Live
        </Badge>
      </div>
      <div className="grid-paper relative">
        <FederationGraph phase={current.phase} round={round} className="aspect-square w-full sm:aspect-[4/3]" />
      </div>
      <figcaption
        className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-[13px]"
        aria-live="off"
      >
        <span className="text-ink">{current.label}</span>
        <span className="font-mono text-2xs text-ink-3">
          {reduce ? "" : `${step + 1}/${CYCLE.length}`}
        </span>
      </figcaption>
    </figure>
  );
}
