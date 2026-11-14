"use client";

import { useEffect, useRef } from "react";
import type { ThemeColors } from "@/lib/useThemeColors";
import { createFederationScene, SITES, type FederationSceneHandle, type ScenePhase } from "./scene";

export type { ScenePhase } from "./scene";

export interface FederationSceneProps {
  colors: ThemeColors;
  phase: ScenePhase;
  /** False while scrolled away: the render loop stops. */
  active: boolean;
  round: number;
  className?: string;
}

const SITE_STATUS: Record<ScenePhase, string> = {
  training: "training on site",
  uploading: "sending update",
  aggregating: "waiting",
  distributing: "receiving model",
};

/** React host for the three.js federation scene in ./scene, plus its labels. */
export default function FederationScene({ colors, phase, active, round, className = "" }: FederationSceneProps) {
  const host = useRef<HTMLDivElement>(null);
  const labels = useRef<(HTMLDivElement | null)[]>([]);
  const handle = useRef<FederationSceneHandle | null>(null);
  const initialColors = useRef(colors);

  useEffect(() => {
    if (!host.current) return;
    const scene = createFederationScene(host.current, initialColors.current);
    scene.setLabels(labels.current);
    handle.current = scene;
    return () => {
      scene.dispose();
      handle.current = null;
    };
  }, []);

  useEffect(() => handle.current?.setColors(colors), [colors]);
  useEffect(() => handle.current?.setPhase(phase), [phase]);
  useEffect(() => handle.current?.setActive(active), [active]);

  const aggregating = phase === "aggregating";

  return (
    <div className={`absolute inset-0 ${className}`}>
      {/* The radial mask fades the floor grid out instead of cutting it at the box edge. */}
      <div ref={host} className="absolute inset-0 [mask-image:radial-gradient(closest-side,black_72%,transparent)]" />
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        {SITES.map((site, i) => (
          <div
            key={site.id}
            ref={(el) => {
              labels.current[i] = el;
            }}
            className="absolute left-0 top-0 whitespace-nowrap rounded-md border border-line bg-surface/90 px-1.5 py-0.5 shadow-raise backdrop-blur-sm will-change-transform sm:px-2 sm:py-1"
          >
            <p className="text-[10px] font-semibold leading-tight text-ink sm:text-[11px]">{site.label}</p>
            {/* Phones get the name only; five status lines crowd a small stage. */}
            <p
              className={`hidden font-mono text-[10px] leading-tight transition-colors sm:block ${
                phase === "training" ? "text-accent-ink" : "text-ink-3"
              }`}
            >
              {SITE_STATUS[phase]}
            </p>
          </div>
        ))}
        <div
          ref={(el) => {
            labels.current[SITES.length] = el;
          }}
          className={`absolute left-0 top-0 z-30 whitespace-nowrap rounded-md border px-2 py-1 font-mono text-[10px] shadow-raise transition-colors will-change-transform ${
            aggregating ? "border-accent bg-accent text-accent-on" : "border-ink/80 bg-ink text-canvas"
          }`}
        >
          <span className="hidden sm:inline">Aggregator · </span>FedAvg · R{round}
        </div>
      </div>
    </div>
  );
}
