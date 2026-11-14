"use client";

import { useEffect, useState } from "react";

let webglSupport: boolean | null = null;

/** One throwaway context, checked once per page load. */
function hasWebGL(): boolean {
  if (webglSupport !== null) return webglSupport;
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    webglSupport = !!gl;
    // Free the context now rather than waiting for garbage collection;
    // browsers cap how many can be alive at once.
    (gl as WebGLRenderingContext | null)?.getExtension("WEBGL_lose_context")?.loseContext();
  } catch {
    webglSupport = false;
  }
  return webglSupport;
}

/**
 * Whether to show a live 3D scene: WebGL works and the visitor has not asked
 * for reduced motion. `null` until checked on the client, so the server
 * render and first paint can show the static fallback without a mismatch.
 */
export function useCan3D(): boolean | null {
  const [can, setCan] = useState<boolean | null>(null);

  useEffect(() => {
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setCan(hasWebGL() && !motion.matches);
    update();
    motion.addEventListener("change", update);
    return () => motion.removeEventListener("change", update);
  }, []);

  return can;
}
