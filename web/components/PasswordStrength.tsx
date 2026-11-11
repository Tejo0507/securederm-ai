"use client";

import { assessPassword, type Assessment } from "@/lib/password";

// Weak to strong runs red, amber, then the brand green.
const BAR: Record<number, string> = {
  0: "bg-danger",
  1: "bg-danger",
  2: "bg-warn",
  3: "bg-accent/70",
  4: "bg-accent",
};

const TEXT: Record<number, string> = {
  0: "text-danger-ink",
  1: "text-danger-ink",
  2: "text-warn-ink",
  3: "text-accent-ink",
  4: "text-accent-ink",
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
  const level = result.blocked ? 0 : result.score;
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
        className="grid grid-cols-4 gap-1"
      >
        {[1, 2, 3, 4].map((segment) => (
          <span
            key={segment}
            className={`h-1 rounded-full transition-colors duration-300 ${segment <= filled ? BAR[level] : "bg-line"}`}
          />
        ))}
      </div>
      <p className="mt-1.5 text-xs leading-relaxed">
        <span className={`font-medium ${TEXT[level]}`}>{result.label}</span>
        {result.advice && <span className="text-ink-3"> · {result.advice}</span>}
      </p>
    </div>
  );
}
