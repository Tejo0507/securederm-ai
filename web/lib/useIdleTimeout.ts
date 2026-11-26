"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart", "scroll"] as const;
const SHARED_KEY = "securederm.lastActivity";
/** When someone last chose "Stay signed in", in any tab. */
const STAYED_KEY = "securederm.stayedSignedInAt";
const WRITE_THROTTLE_MS = 5_000;
const TICK_MS = 1_000;

export interface IdleState {
  /** Whole seconds until sign-out while the warning is showing, otherwise null. */
  secondsLeft: number | null;
  /** The person chose to stay: restart the idle clock and hide the warning. */
  stay: () => void;
}

function readShared(key: string): number {
  try {
    return Number(localStorage.getItem(key)) || 0;
  } catch {
    return 0;   // storage blocked: this tab's own activity is all we have
  }
}

function writeShared(key: string, at: number): void {
  try {
    localStorage.setItem(key, String(at));
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
 *   it: only `stay()` does, so an unattended screen still signs out. `stay()`
 *   in one tab dismisses the warning in all of them, since signing out any one
 *   tab ends the session for every tab.
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
      writeShared(SHARED_KEY, now);
    }
  }, []);

  const stay = useCallback(() => {
    warning.current = false;
    setSecondsLeft(null);
    lastWrite.current = 0;
    touch();
    writeShared(STAYED_KEY, lastActivity.current);
  }, [touch]);

  useEffect(() => {
    if (!enabled) return;
    lastActivity.current = Date.now();
    writeShared(SHARED_KEY, lastActivity.current);

    const onActivity = () => {
      if (!warning.current) touch();
    };
    ACTIVITY_EVENTS.forEach((name) =>
      window.addEventListener(name, onActivity, { passive: true, capture: true }),
    );

    const timer = window.setInterval(() => {
      // Another tab's activity counts too. While this tab is warning, only a
      // deliberate "Stay signed in" elsewhere does.
      const last = Math.max(
        lastActivity.current,
        readShared(warning.current ? STAYED_KEY : SHARED_KEY),
      );
      const idle = Date.now() - last;
      if (idle >= timeoutMs) {
        window.clearInterval(timer);
        onTimeoutRef.current();
      } else if (idle >= timeoutMs - warnMs) {
        warning.current = true;
        setSecondsLeft(Math.max(1, Math.ceil((timeoutMs - idle) / 1000)));
      } else if (warning.current) {
        warning.current = false;
        lastActivity.current = last;
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
