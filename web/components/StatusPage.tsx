import type { ReactNode } from "react";
import Logo from "@/components/ui/Logo";

/** Centered single-message page used by the 404 and error boundaries. */
export default function StatusPage({
  code,
  title,
  children,
  actions,
}: {
  code: string;
  title: string;
  children: ReactNode;
  actions: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col px-4 py-6 sm:px-10">
      <Logo />
      <main id="main" className="flex flex-1 items-center justify-center py-16">
        <div className="w-full max-w-md animate-fade-up">
          <p className="label-mono text-ink-3">{code}</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.025em] text-ink">{title}</h1>
          <div className="mt-3 text-[15px] leading-relaxed text-ink-2">{children}</div>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">{actions}</div>
        </div>
      </main>
    </div>
  );
}
