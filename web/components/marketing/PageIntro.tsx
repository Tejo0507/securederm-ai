import type { ReactNode } from "react";

/** Title block at the top of the public secondary pages (Models, Demo). */
export default function PageIntro({
  eyebrow,
  title,
  children,
  actions,
}: {
  eyebrow: string;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="border-b border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 pb-10 pt-10 sm:px-6 sm:pt-14 md:flex-row md:items-end md:justify-between">
        <div className="max-w-2xl animate-fade-up">
          <p className="label-mono text-accent-ink">{eyebrow}</p>
          <h1 className="mt-3 text-[2rem] font-semibold leading-tight tracking-[-0.03em] text-ink sm:text-[2.75rem]">
            {title}
          </h1>
          {children && <p className="mt-4 text-[17px] leading-relaxed text-ink-2">{children}</p>}
        </div>
        {actions && <div className="flex shrink-0 gap-3">{actions}</div>}
      </div>
    </div>
  );
}
