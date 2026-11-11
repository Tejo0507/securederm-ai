import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

/** Shared control styling so every input, select and date picker lines up. */
export const controlClass =
  "block w-full rounded border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-3 shadow-[inset_0_1px_0_rgb(var(--shadow)/0.03)] transition-[border-color,box-shadow] duration-150 hover:border-ink-3 focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/20 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger aria-[invalid=true]:focus:ring-danger/20";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { compact?: boolean }>(
  function Input({ className = "", compact = false, ...rest }, ref) {
    return <input ref={ref} className={`${controlClass} ${compact ? "h-8" : "h-10"} ${className}`} {...rest} />;
  },
);

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement> & { compact?: boolean }
>(function Select({ className = "", compact = false, children, ...rest }, ref) {
  return (
    <div className={`relative ${className}`}>
      <select
        ref={ref}
        className={`${controlClass} ${compact ? "h-8" : "h-10"} cursor-pointer appearance-none pr-8`}
        {...rest}
      >
        {children}
      </select>
      <svg
        aria-hidden="true"
        viewBox="0 0 16 16"
        className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="m4 6 4 4 4-4" />
      </svg>
    </div>
  );
});

/** Label, control and the line of help or error text beneath it. */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  aside,
  children,
  className = "",
}: {
  label: ReactNode;
  htmlFor: string;
  hint?: ReactNode;
  error?: ReactNode;
  /** Something to the right of the label, like a "Forgot?" link. */
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <label htmlFor={htmlFor} className="text-[13px] font-medium text-ink">
          {label}
        </label>
        {aside}
      </div>
      {children}
      {error ? (
        <p className="mt-1.5 text-xs text-danger-ink">{error}</p>
      ) : hint ? (
        <div className="mt-1.5 text-xs text-ink-3">{hint}</div>
      ) : null}
    </div>
  );
}
