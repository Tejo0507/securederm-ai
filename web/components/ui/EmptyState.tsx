import type { ReactNode } from "react";

/** What a section shows when it has nothing yet: what goes here, and how to fill it. */
export default function EmptyState({
  icon,
  title,
  children,
  action,
  className = "",
}: {
  icon?: ReactNode;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center rounded border border-dashed border-line-strong bg-canvas/60 px-6 py-10 text-center ${className}`}
    >
      {icon && (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface text-ink-3 shadow-raise">
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-ink-2">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
