import Link from "next/link";

/**
 * The mark: three hospital nodes feeding one shared model, inside a rounded
 * square. Drawn in currentColor so it works on light, dark and accent fills.
 */
export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <rect width="32" height="32" rx="8" fill="currentColor" />
      <g stroke="rgb(var(--canvas))" strokeWidth="1.8" strokeLinecap="round">
        <path d="M9 10.5 16 17M23 10.5 16 17M16 25v-8" opacity="0.55" />
      </g>
      <circle cx="9" cy="10.5" r="2.6" fill="rgb(var(--canvas))" />
      <circle cx="23" cy="10.5" r="2.6" fill="rgb(var(--canvas))" />
      <circle cx="16" cy="25" r="2.6" fill="rgb(var(--canvas))" />
      <circle cx="16" cy="17" r="3.4" fill="rgb(var(--accent))" stroke="rgb(var(--canvas))" strokeWidth="1.6" />
    </svg>
  );
}

export default function Logo({
  href = "/",
  className = "",
  tone = "default",
}: {
  href?: string;
  className?: string;
  tone?: "default" | "night";
}) {
  return (
    <Link
      href={href}
      className={`group inline-flex items-center gap-2.5 rounded ${className}`}
      aria-label="SecureDerm AI home"
    >
      <LogoMark className={`transition-transform duration-300 ease-out group-hover:rotate-[-6deg] ${tone === "night" ? "text-night-ink" : "text-ink"}`} />
      <span className={`text-[15px] font-semibold tracking-[-0.01em] ${tone === "night" ? "text-night-ink" : "text-ink"}`}>
        SecureDerm
        <span className={`ml-1 font-mono text-[11px] font-medium uppercase tracking-[0.08em] ${tone === "night" ? "text-night-muted" : "text-ink-3"}`}>
          AI
        </span>
      </span>
    </Link>
  );
}
