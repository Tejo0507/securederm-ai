/**
 * Times the API stores without a zone ("2026-11-18T14:21:40") are UTC. `new Date`
 * reads a string like that as *local* time, so every such time showed hours off
 * in any zone but UTC. Strings that already carry a zone ("...Z", "+00:00")
 * are left alone.
 */
export function parseServerTime(ts: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(ts);
  return new Date(hasZone ? ts : `${ts}Z`);
}

/** A server timestamp as a local date and time, or `fallback` when there is none. */
export function formatServerTime(ts: string | null | undefined, fallback = "Not recorded"): string {
  return ts ? parseServerTime(ts).toLocaleString() : fallback;
}

/** A server timestamp as a local date only, or `fallback` when there is none. */
export function formatServerDate(ts: string | null | undefined, fallback = "Not recorded"): string {
  return ts ? parseServerTime(ts).toLocaleDateString() : fallback;
}
