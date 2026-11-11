/**
 * Password feedback shown while typing, so people learn *before* submitting
 * that a password will be refused. It mirrors the server's rules (minimum
 * length, a blocklist of very common passwords) and adds advice the server
 * does not enforce. The server stays the authority: this only informs.
 */
export const MIN_PASSWORD_LENGTH = 8;

// Same list as _COMMON_WEAK_PASSWORDS in web_backend/schemas.py.
const COMMON_PASSWORDS = new Set([
  "password", "password1", "password123", "12345678", "123456789",
  "1234567890", "qwerty123", "letmein123", "welcome123", "admin1234",
  "iloveyou1", "sunshine1", "princess1", "football1", "baseball1",
  "changeme1", "abc123456", "correcthorsebatterystaple",
]);

const PATTERNS = ["qwerty", "asdf", "zxcv", "12345", "abcde", "password", "letmein", "admin"];

export type Strength = 0 | 1 | 2 | 3 | 4;

export interface Assessment {
  score: Strength;
  label: "Too weak" | "Weak" | "Fair" | "Good" | "Strong";
  /** True when the server would refuse it (too short or too common). */
  blocked: boolean;
  /** The single most useful thing to change, or "" when there is nothing to add. */
  advice: string;
}

const LABELS: Assessment["label"][] = ["Too weak", "Weak", "Fair", "Good", "Strong"];

/** Lower-cased words (4+ letters) from the person's own details. */
function personalWords(personal: string[]): string[] {
  return personal
    .flatMap((value) => value.toLowerCase().split(/[^a-z0-9]+/))
    .filter((word) => word.length >= 4);
}

export function assessPassword(password: string, personal: string[] = []): Assessment {
  if (password.length === 0) {
    return { score: 0, label: "Too weak", blocked: true, advice: "" };
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    return {
      score: 0,
      label: "Too weak",
      blocked: true,
      advice: `Use at least ${MIN_PASSWORD_LENGTH} characters (${MIN_PASSWORD_LENGTH - password.length} more).`,
    };
  }
  const lower = password.toLowerCase();
  if (COMMON_PASSWORDS.has(lower)) {
    return {
      score: 0,
      label: "Too weak",
      blocked: true,
      advice: "This password is too common. Choose a less predictable one.",
    };
  }

  const classes =
    Number(/[a-z]/.test(password)) +
    Number(/[A-Z]/.test(password)) +
    Number(/\d/.test(password)) +
    Number(/[^A-Za-z0-9]/.test(password));
  const distinct = new Set(password).size;

  // Length is the main factor; mixing character types and not repeating the
  // same few characters add to it.
  let score = password.length >= 16 ? 3 : password.length >= 12 ? 2 : 1;
  if (classes >= 3) score += 1;
  if (distinct <= Math.ceil(password.length / 3)) score -= 1;

  let advice = "";
  const containsPersonal = personalWords(personal).some((word) => lower.includes(word));
  if (containsPersonal) {
    score = Math.min(score, 1);
    advice = "Avoid using your name, email or hospital name in the password.";
  } else if (PATTERNS.some((pattern) => lower.includes(pattern)) || /(.)\1{3,}/.test(password)) {
    score = Math.min(score, 1);
    advice = "Avoid keyboard runs, repeated characters and common words.";
  } else if (password.length < 12) {
    advice = "Longer is stronger: try 12 or more characters, or a short phrase.";
  } else if (classes < 3) {
    advice = "Mix in capitals, numbers or symbols to make it harder to guess.";
  }

  const clamped = Math.max(0, Math.min(4, score)) as Strength;
  return { score: clamped, label: LABELS[clamped], blocked: false, advice };
}
