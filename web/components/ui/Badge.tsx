import type { ReactNode } from "react";

type Tone = "neutral" | "accent" | "warning" | "danger" | "success";

const tones: Record<Tone, string> = {
  neutral: "border-line-strong bg-sunken text-ink-2",
  accent: "border-accent/25 bg-accent-soft text-accent-ink",
  warning: "border-warn/30 bg-warn-soft text-warn-ink",
  danger: "border-danger/25 bg-danger-soft text-danger-ink",
  success: "border-ok/25 bg-ok-soft text-ok-ink",
};

const dots: Record<Tone, string> = {
  neutral: "bg-ink-3",
  accent: "bg-accent",
  warning: "bg-warn",
  danger: "bg-danger",
  success: "bg-ok",
};

/** Small status pill. The dot repeats the tone so color is never the only signal next to its text. */
export default function Badge({
  tone = "neutral",
  dot = false,
  pulse = false,
  children,
  className = "",
}: {
  tone?: Tone;
  dot?: boolean;
  pulse?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 text-xs font-medium ${tones[tone]} ${className}`}
    >
      {dot && (
        <span className="relative flex h-1.5 w-1.5">
          {pulse && (
            <span className={`absolute inset-0 animate-ping rounded-full opacity-60 motion-reduce:hidden ${dots[tone]}`} />
          )}
          <span className={`relative h-1.5 w-1.5 rounded-full ${dots[tone]}`} />
        </span>
      )}
      {children}
    </span>
  );
}
