/**
 * Detecting that the signed-in session has ended, and letting the page that
 * cares (the dashboard) react once, centrally, instead of every tab showing its
 * own cryptic error.
 *
 * Not every 401 means that: changing a password or deleting an account with the
 * wrong current password also answers 401. The backend's session failures use
 * these exact messages, so match on them rather than on the status alone.
 */
export const SESSION_ENDED_MESSAGES: readonly string[] = [
  "Not authenticated",
  "Invalid or expired token",
  "Session has been signed out",
  "Hospital not found",
];

export function isSessionEnded(status: number, message: string): boolean {
  return status === 401 && SESSION_ENDED_MESSAGES.includes(message);
}

type Handler = () => void;
let handler: Handler | null = null;
let notified = false;

/** Register the page-level reaction; returns the function that unregisters it. */
export function onSessionEnded(fn: Handler): () => void {
  handler = fn;
  notified = false;
  return () => {
    if (handler === fn) handler = null;
  };
}

/** Called by the API client. Several requests can fail together; react once. */
export function notifySessionEnded(): void {
  if (!handler || notified) return;
  notified = true;
  handler();
}

/**
 * The user just ended the session on purpose (logout, password change, sign
 * out everywhere, account deletion). Polls that fail a moment later must not be
 * reported as "your session expired".
 */
export function expectSessionEnd(): void {
  notified = true;
}

/** Where to send someone whose session ended, with a reason the login page shows. */
export const SESSION_ENDED_REDIRECT = "/login?reason=expired";
