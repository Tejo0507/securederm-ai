"use client";

import { assessPassword, type Assessment } from "@/lib/password";

const COLORS: Record<number, string> = {
  0: "bg-rose-500",
  1: "bg-orange-500",
  2: "bg-amber-400",
  3: "bg-lime-400",
  4: "bg-emerald-400",
};

const TEXT_COLORS: Record<number, string> = {
  0: "text-rose-400",
  1: "text-orange-400",
  2: "text-amber-300",
  3: "text-lime-300",
  4: "text-emerald-300",
};

/**
 * A four-segment strength meter with one line of advice. Renders nothing until
 * the person starts typing. Announced politely to screen readers as it changes.
 * `personal` lists the user's own details (name, email) the password must not echo.
 */
export default function PasswordStrength({
  password,
  personal = [],
  id,
}: {
  password: string;
  personal?: string[];
  id?: string;
}) {
  if (password.length === 0) return null;
  const result: Assessment = assessPassword(password, personal);
  const filled = result.blocked ? 1 : Math.max(1, result.score);

  return (
    <div id={id} className="mt-2" aria-live="polite">
      <div
        role="meter"
        aria-label="Password strength"
        aria-valuemin={0}
        aria-valuemax={4}
        aria-valuenow={result.score}
        aria-valuetext={result.label}
        className="flex gap-1"
      >
        {[1, 2, 3, 4].map((segment) => (
          <span
            key={segment}
            className={`h-1.5 flex-1 rounded-full transition-colors ${
              segment <= filled ? COLORS[result.blocked ? 0 : result.score] : "bg-white/10"
            }`}
          />
        ))}
      </div>
      <p className="mt-1.5 text-xs">
        <span className={`font-medium ${TEXT_COLORS[result.blocked ? 0 : result.score]}`}>
          {result.label}
        </span>
        {result.advice && <span className="text-zinc-500"> · {result.advice}</span>}
      </p>
    </div>
  );
}
