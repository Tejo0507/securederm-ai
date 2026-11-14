"use client";

import { useEffect, useRef } from "react";
import type { ThemeColors } from "@/lib/useThemeColors";
import { createFederationScene, type FederationSceneHandle, type ScenePhase } from "./scene";

export type { ScenePhase } from "./scene";

export interface FederationSceneProps {
  colors: ThemeColors;
  phase: ScenePhase;
  /** False while scrolled away: the render loop stops. */
  active: boolean;
  className?: string;
}

/** React host for the three.js federation scene in ./scene. */
export default function FederationScene({ colors, phase, active, className = "" }: FederationSceneProps) {
  const host = useRef<HTMLDivElement>(null);
  const handle = useRef<FederationSceneHandle | null>(null);
  const initialColors = useRef(colors);

  useEffect(() => {
    if (!host.current) return;
    const scene = createFederationScene(host.current, initialColors.current);
    handle.current = scene;
    return () => {
      scene.dispose();
      handle.current = null;
    };
  }, []);

  useEffect(() => handle.current?.setColors(colors), [colors]);
  useEffect(() => handle.current?.setPhase(phase), [phase]);
  useEffect(() => handle.current?.setActive(active), [active]);

  // The radial mask fades the floor grid out instead of cutting it at the box edge.
  return (
    <div
      ref={host}
      className={`absolute inset-0 [mask-image:radial-gradient(closest-side,black_72%,transparent)] ${className}`}
    />
  );
}
