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
import { buttonClass } from "@/components/ui/Button";
import { IconAlert } from "@/components/ui/icons";

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
      className="fixed inset-0 z-[100] flex items-end justify-center bg-ink/40 p-4 backdrop-blur-[2px] sm:items-center dark:bg-black/60"
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
        initial={{ opacity: 0, scale: 0.98, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.98, y: 6 }}
        transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-float"
      >
        <div className="flex gap-4">
          {options.danger && (
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-danger-soft text-danger-ink">
              <IconAlert size={18} />
            </span>
          )}
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold tracking-[-0.01em] text-ink">
              {options.title}
            </h2>
            <p id={messageId} className="mt-1.5 text-sm leading-relaxed text-ink-2">
              {options.message}
            </p>
          </div>
        </div>
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref={cancelButton}
            type="button"
            onClick={() => onClose(false)}
            className={buttonClass("secondary", "md")}
          >
            {options.cancelLabel ?? "Cancel"}
          </button>
          <button
            type="button"
            onClick={() => onClose(true)}
            className={buttonClass(options.danger ? "danger" : "primary", "md")}
          >
            {options.confirmLabel ?? "Confirm"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
