import type { ReactNode } from "react";
import Link from "next/link";
import Logo from "@/components/ui/Logo";
import { IconCheck } from "@/components/ui/icons";

const POINTS = [
  "Patient images never leave your hospital's node",
  "Every weight update is clipped and noised before it is shared",
  "Signed-in sessions end on their own after inactivity",
];

/**
 * Two-column frame for sign-in, sign-up and email verification: the form on
 * the left, a quiet statement of the privacy model on the right (desktop only).
 */
export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_minmax(420px,0.85fr)]">
      <div className="flex flex-col px-4 py-6 sm:px-10">
        <div className="flex items-center justify-between">
          <Logo />
          <Link href="/" className="text-[13px] text-ink-2 transition-colors hover:text-ink">
            Back to site
          </Link>
        </div>

        <main id="main" className="flex flex-1 items-center justify-center py-12">
          <div className="w-full max-w-[400px] animate-fade-up">
            <h1 className="text-[1.75rem] font-semibold leading-tight tracking-[-0.025em] text-ink">{title}</h1>
            {subtitle && <p className="mt-2 text-[15px] leading-relaxed text-ink-2">{subtitle}</p>}
            <div className="mt-8">{children}</div>
            {footer && <div className="mt-8 border-t border-line pt-6 text-sm text-ink-2">{footer}</div>}
          </div>
        </main>

        <p className="text-xs text-ink-3">&copy; {new Date().getFullYear()} SecureDerm AI</p>
      </div>

      <aside className="relative hidden overflow-hidden bg-night lg:block" aria-label="About SecureDerm">
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-40 [background-image:linear-gradient(rgb(var(--night-line))_1px,transparent_1px),linear-gradient(90deg,rgb(var(--night-line))_1px,transparent_1px)] [background-size:40px_40px] [mask-image:radial-gradient(ellipse_at_70%_30%,black,transparent_75%)]"
        />
        <div className="relative flex h-full flex-col justify-between p-12 xl:p-16">
          <p className="label-mono text-night-muted">Federated · differentially private</p>
          <div>
            <p className="max-w-md text-[2rem] font-semibold leading-[1.15] tracking-[-0.025em] text-night-ink">
              A shared wound model, built without sharing a single image.
            </p>
            <ul className="mt-10 space-y-4">
              {POINTS.map((p) => (
                <li key={p} className="flex items-start gap-3 text-[15px] text-night-muted">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-night-line text-accent">
                    <IconCheck size={12} />
                  </span>
                  {p}
                </li>
              ))}
            </ul>
          </div>
          <p className="font-mono text-2xs text-night-muted">FedAvg · ResNet-18 · ε-DP</p>
        </div>
      </aside>
    </div>
  );
}
