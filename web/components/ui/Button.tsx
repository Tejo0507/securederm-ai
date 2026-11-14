import { forwardRef, type ButtonHTMLAttributes } from "react";
import Spinner from "@/components/ui/Spinner";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "danger-quiet" | "inverse";
export type ButtonSize = "sm" | "md" | "lg";

const base =
  "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded font-medium transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out disabled:pointer-events-none disabled:opacity-45";

/*
 * Solid buttons sit on an edge (shadow-edge-*): hover lifts them a pixel,
 * pressing pushes them down onto a flat shadow, like a physical key.
 */
const press = "hover:-translate-y-px active:translate-y-[3px] active:shadow-pressed";

const variants: Record<ButtonVariant, string> = {
  primary: `bg-accent text-accent-on shadow-edge-accent hover:bg-accent-hover ${press}`,
  secondary: `border border-line-strong bg-surface text-ink shadow-edge-neutral hover:border-ink-3 hover:bg-sunken ${press}`,
  ghost: "text-ink-2 hover:bg-ink/[0.06] hover:text-ink active:translate-y-px",
  danger: `bg-danger text-white shadow-edge-danger hover:bg-danger-hover dark:text-canvas ${press}`,
  "danger-quiet": `border border-danger/30 bg-surface text-danger-ink shadow-edge-neutral hover:border-danger/60 hover:bg-danger-soft ${press}`,
  inverse: `bg-night-ink text-night shadow-edge-inverse hover:bg-white ${press}`,
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-5 text-[15px]",
};

/** Class string for anything that should look like a button (links included). */
export function buttonClass(variant: ButtonVariant = "primary", size: ButtonSize = "md", extra = "") {
  return `${base} ${variants[variant]} ${sizes[size]} ${extra}`;
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner and blocks clicks while an action is in flight. */
  loading?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, className = "", type = "button", disabled, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClass(variant, size, className)}
      {...rest}
    >
      {loading && <Spinner size={size === "sm" ? 12 : 14} />}
      {children}
    </button>
  );
});

export default Button;
