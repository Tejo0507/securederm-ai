import type { ReactNode } from "react";

/** The heading row of a dashboard section: the page's single h1, a description and actions. */
export default function SectionHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 max-w-2xl">
        <h1 className="truncate text-2xl font-semibold tracking-[-0.025em] text-ink sm:text-[1.75rem]">{title}</h1>
        {description && <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
