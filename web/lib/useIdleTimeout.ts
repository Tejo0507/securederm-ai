"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart", "scroll"] as const;
const SHARED_KEY = "securederm.lastActivity";
const WRITE_THROTTLE_MS = 5_000;
const TICK_MS = 1_000;

export interface IdleState {
  /** Whole seconds until sign-out while the warning is showing, otherwise null. */
  secondsLeft: number | null;
  /** The person chose to stay: restart the idle clock and hide the warning. */
  stay: () => void;
}

function readShared(): number {
  try {
    return Number(localStorage.getItem(SHARED_KEY)) || 0;
  } catch {
    return 0;   // storage blocked: this tab's own activity is all we have
  }
}

function writeShared(at: number): void {
  try {
    localStorage.setItem(SHARED_KEY, String(at));
  } catch {
    // ignore
  }
}

/**
 * Signs an unattended workstation out. After `timeoutMs` without input the user
 * gets `warnMs` of warning, then `onTimeout` runs.
 *
 * - Activity in *any* tab of this browser counts (via localStorage), so working
 *   in one tab never signs out another.
 * - While the warning is up, passive activity (a nudged mouse) does not dismiss
 *   it: only `stay()` does, so an unattended screen still signs out.
 * - Time is measured against the clock, not by counting ticks, so a laptop that
 *   slept or a throttled background tab is still signed out on schedule.
 */
export function useIdleTimeout(
  enabled: boolean,
  timeoutMs: number,
  warnMs: number,
  onTimeout: () => void,
): IdleState {
  const lastActivity = useRef(Date.now());
  const lastWrite = useRef(0);
  const warning = useRef(false);
  const onTimeoutRef = useRef(onTimeout);
  onTimeoutRef.current = onTimeout;
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  const touch = useCallback(() => {
    const now = Date.now();
    lastActivity.current = now;
    if (now - lastWrite.current > WRITE_THROTTLE_MS) {
      lastWrite.current = now;
      writeShared(now);
    }
  }, []);

  const stay = useCallback(() => {
    warning.current = false;
    setSecondsLeft(null);
    lastWrite.current = 0;
    touch();
  }, [touch]);

  useEffect(() => {
    if (!enabled) return;
    lastActivity.current = Date.now();
    writeShared(lastActivity.current);

    const onActivity = () => {
      if (!warning.current) touch();
    };
    ACTIVITY_EVENTS.forEach((name) =>
      window.addEventListener(name, onActivity, { passive: true, capture: true }),
    );

    const timer = window.setInterval(() => {
      // Another tab's activity counts too, but never while this tab is warning.
      const last = warning.current
        ? lastActivity.current
        : Math.max(lastActivity.current, readShared());
      const idle = Date.now() - last;
      if (idle >= timeoutMs) {
        window.clearInterval(timer);
        onTimeoutRef.current();
      } else if (idle >= timeoutMs - warnMs) {
        warning.current = true;
        setSecondsLeft(Math.max(1, Math.ceil((timeoutMs - idle) / 1000)));
      } else if (warning.current) {
        warning.current = false;
        setSecondsLeft(null);
      }
    }, TICK_MS);

    return () => {
      window.clearInterval(timer);
      ACTIVITY_EVENTS.forEach((name) =>
        window.removeEventListener(name, onActivity, { capture: true }),
      );
    };
  }, [enabled, timeoutMs, warnMs, touch]);

  return { secondsLeft, stay };
}
