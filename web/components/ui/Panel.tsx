import type { HTMLAttributes, ReactNode } from "react";

/** The one container style used across the app: white sheet, hairline border, slight lift. */
export function Panel({
  children,
  className = "",
  as: Tag = "section",
  tone = "default",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "form" | "article";
  tone?: "default" | "danger";
} & Omit<HTMLAttributes<HTMLElement>, "children" | "className">) {
  const border = tone === "danger" ? "border-danger/25" : "border-line";
  return (
    <Tag className={`rounded-lg border ${border} bg-surface shadow-raise ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

/** Title row inside a panel, with optional description and actions on the right. */
export function PanelHeader({
  title,
  description,
  actions,
  id,
  className = "",
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  id?: string;
  className?: string;
}) {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-x-6 gap-y-3 px-5 pt-5 sm:px-6 ${className}`}>
      <div className="min-w-0 max-w-2xl">
        <h2 id={id} className="text-[15px] font-semibold tracking-[-0.01em] text-ink">
          {title}
        </h2>
        {description && <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function PanelBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-5 pb-5 pt-4 sm:px-6 sm:pb-6 ${className}`}>{children}</div>;
}

/** A row of key figures separated by hairlines, instead of a grid of floating cards. */
export function StatStrip({
  stats,
  className = "",
}: {
  stats: { label: string; value: ReactNode; hint?: ReactNode }[];
  className?: string;
}) {
  return (
    <dl
      className={`grid grid-cols-2 overflow-hidden rounded-lg border border-line bg-surface shadow-raise lg:grid-cols-4 ${className}`}
    >
      {stats.map((s, i) => (
        <div
          key={s.label}
          className={`min-w-0 px-5 py-4 sm:px-6 sm:py-5 ${i % 2 === 1 ? "border-l border-line" : ""} ${
            i >= 2 ? "border-t border-line lg:border-t-0" : ""
          } ${i === 2 ? "lg:border-l" : ""}`}
        >
          <dt className="label-mono text-ink-3">{s.label}</dt>
          <dd className="mt-2 truncate text-2xl font-semibold tracking-[-0.02em] text-ink tabular">{s.value}</dd>
          {s.hint && <dd className="mt-1 truncate text-xs text-ink-3">{s.hint}</dd>}
        </div>
      ))}
    </dl>
  );
}
