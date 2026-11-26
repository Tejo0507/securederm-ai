import type { HospitalInfo } from "@/lib/types";

/**
 * The signed-in hospital's display details, cached for a quick first paint.
 *
 * Only a convenience: the session itself lives in an httpOnly cookie. Browsers
 * that block site data throw on any localStorage access, so every call here
 * swallows that. Sign-in must not report failure because a cache write did.
 */
const KEY = "hospital";

export function readCachedHospital(): HospitalInfo | null {
  try {
    const stored = localStorage.getItem(KEY);
    return stored ? (JSON.parse(stored) as HospitalInfo) : null;
  } catch {
    clearCachedHospital(); // corrupt entry: don't keep tripping over it
    return null;
  }
}

export function cacheHospital(hospital: HospitalInfo): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(hospital));
  } catch {
    // storage blocked or full; the next page asks the server instead
  }
}

export function clearCachedHospital(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // storage blocked; nothing cached to clear
  }
}
