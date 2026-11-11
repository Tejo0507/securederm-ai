import type { ReactNode } from "react";
import { IconAlert, IconCheck, IconInfo } from "@/components/ui/icons";

type Tone = "info" | "success" | "warning" | "danger";

const tones: Record<Tone, { box: string; icon: ReactNode }> = {
  info: { box: "border-line-strong bg-sunken text-ink-2", icon: <IconInfo size={16} /> },
  success: { box: "border-ok/25 bg-ok-soft text-ok-ink", icon: <IconCheck size={16} /> },
  warning: { box: "border-warn/30 bg-warn-soft text-warn-ink", icon: <IconAlert size={16} /> },
  danger: { box: "border-danger/25 bg-danger-soft text-danger-ink", icon: <IconAlert size={16} /> },
};

/**
 * An inline message box. `role` decides how screen readers hear it: "alert" for
 * errors the person must act on, "status" for confirmations.
 */
export default function Notice({
  tone = "info",
  title,
  children,
  role,
  className = "",
}: {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  role?: "alert" | "status";
  className?: string;
}) {
  const t = tones[tone];
  return (
    <div role={role} className={`flex gap-2.5 rounded border px-3.5 py-2.5 text-[13px] leading-relaxed ${t.box} ${className}`}>
      <span className="mt-[3px] shrink-0">{t.icon}</span>
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={title ? "mt-0.5 opacity-90" : ""}>{children}</div>}
      </div>
    </div>
  );
}

/** One-line inline feedback next to a button ("Saved." / an error). */
export function InlineStatus({ error, children }: { error?: boolean; children: ReactNode }) {
  return (
    <span
      role={error ? "alert" : "status"}
      className={`inline-flex items-center gap-1.5 text-[13px] ${error ? "text-danger-ink" : "text-ok-ink"}`}
    >
      {error ? <IconAlert size={14} /> : <IconCheck size={14} />}
      {children}
    </span>
  );
}
