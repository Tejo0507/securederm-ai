"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { buttonClass } from "@/components/ui/Button";
import { IconLock } from "@/components/ui/icons";

/**
 * "You'll be signed out soon" dialog. Staying signed in is a deliberate click or
 * keypress; the primary button takes focus so Enter or Space is enough.
 */
export default function IdleWarning({
  secondsLeft,
  onStay,
  onSignOut,
}: {
  secondsLeft: number | null;
  onStay: () => void;
  onSignOut: () => void;
}) {
  const stayButton = useRef<HTMLButtonElement>(null);
  const open = secondsLeft !== null;

  useEffect(() => {
    if (open) stayButton.current?.focus();
  }, [open]);

  const minutes = Math.floor((secondsLeft ?? 0) / 60);
  const seconds = (secondsLeft ?? 0) % 60;
  const clock = `${minutes}:${String(seconds).padStart(2, "0")}`;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="idle-warning"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[110] flex items-end justify-center bg-ink/50 p-4 backdrop-blur-sm sm:items-center dark:bg-black/70"
        >
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="idle-title"
            aria-describedby="idle-message"
            className="w-full max-w-md overflow-hidden rounded-xl border border-line bg-surface shadow-float"
          >
            <div className="flex items-center justify-between border-b border-line bg-warn-soft px-6 py-4">
              <span className="flex items-center gap-2 text-sm font-medium text-warn-ink">
                <IconLock size={16} />
                Automatic sign-out
              </span>
              <span className="font-mono text-2xl font-medium tabular text-warn-ink" aria-hidden="true">
                {clock}
              </span>
            </div>
            <div className="p-6">
              <h2 id="idle-title" className="text-base font-semibold text-ink">
                Still there?
              </h2>
              <p id="idle-message" className="mt-1.5 text-sm leading-relaxed text-ink-2">
                For your patients&apos; privacy you will be signed out after a period of inactivity
                <span className="sr-only">{`, in ${minutes} minutes ${seconds} seconds`}</span>.
              </p>
              <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <button type="button" onClick={onSignOut} className={buttonClass("secondary")}>
                  Sign out now
                </button>
                <button ref={stayButton} type="button" onClick={onStay} className={buttonClass("primary")}>
                  Stay signed in
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
