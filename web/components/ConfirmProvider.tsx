"use client";

import {
  KeyboardEvent,
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { AnimatePresence, motion } from "framer-motion";

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Styles the confirm button as destructive. */
  danger?: boolean;
}

type Confirm = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<Confirm | null>(null);

/**
 * `const confirm = useConfirm(); if (!(await confirm({...}))) return;`
 *
 * Replaces window.confirm, which cannot be styled, blocks the page, says
 * nothing useful to a screen reader about what is being confirmed, and which
 * browsers let users suppress (making a destructive action silently proceed).
 */
export function useConfirm(): Confirm {
  const confirm = useContext(ConfirmContext);
  if (!confirm) throw new Error("useConfirm must be used inside <ConfirmProvider>");
  return confirm;
}

interface Pending extends ConfirmOptions {
  resolve: (ok: boolean) => void;
}

export default function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const opener = useRef<HTMLElement | null>(null);

  const confirm = useCallback<Confirm>(
    (options) =>
      new Promise<boolean>((resolve) => {
        opener.current = document.activeElement as HTMLElement | null;
        // A second request while one is open cancels the first rather than stacking.
        setPending((current) => {
          current?.resolve(false);
          return { ...options, resolve };
        });
      }),
    [],
  );

  const close = useCallback((ok: boolean) => {
    setPending((current) => {
      current?.resolve(ok);
      return null;
    });
    // Hand focus back to whatever opened the dialog.
    opener.current?.focus?.();
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <AnimatePresence>
        {pending && <Dialog key="confirm" options={pending} onClose={close} />}
      </AnimatePresence>
    </ConfirmContext.Provider>
  );
}

function Dialog({
  options,
  onClose,
}: {
  options: ConfirmOptions;
  onClose: (ok: boolean) => void;
}) {
  const titleId = useId();
  const messageId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);

  // Cancel is focused first: with a destructive action, an accidental Enter
  // should be the safe choice.
  useEffect(() => {
    cancelButton.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose(false);
      return;
    }
    if (e.key !== "Tab") return;
    // Keep keyboard focus inside the dialog while it is open.
    const focusable = panel.current?.querySelectorAll<HTMLElement>("button:not([disabled])");
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose(false);
      }}
      onKeyDown={onKeyDown}
    >
      <motion.div
        ref={panel}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97 }}
        transition={{ duration: 0.15 }}
        className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-900 p-6 shadow-2xl"
      >
        <h2 id={titleId} className="text-lg font-semibold text-white">
          {options.title}
        </h2>
        <p id={messageId} className="mt-2 text-sm text-zinc-400">
          {options.message}
        </p>
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref={cancelButton}
            type="button"
            onClick={() => onClose(false)}
            className="px-4 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-zinc-200 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/70 transition-colors"
          >
            {options.cancelLabel ?? "Cancel"}
          </button>
          <button
            type="button"
            onClick={() => onClose(true)}
            className={`px-4 py-2 rounded-lg text-sm font-medium text-white focus-visible:outline-none focus-visible:ring-2 transition-colors ${
              options.danger
                ? "bg-rose-600 hover:bg-rose-500 focus-visible:ring-rose-300/70"
                : "bg-indigo-600 hover:bg-indigo-500 focus-visible:ring-indigo-300/70"
            }`}
          >
            {options.confirmLabel ?? "Confirm"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
