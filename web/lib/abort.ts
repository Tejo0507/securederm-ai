/**
 * One signal that aborts when any of `signals` does.
 *
 * `AbortSignal.any` is the built-in way, but it only exists in Chrome 116+,
 * Firefox 124+ and Safari 17.4+. Calling it elsewhere throws a TypeError, which
 * would break every request that passes its own signal, so fall back to wiring
 * the signals together by hand.
 */
export function anySignal(signals: AbortSignal[]): AbortSignal {
  if (typeof AbortSignal.any === "function") return AbortSignal.any(signals);

  const combined = new AbortController();
  const abort = (from: AbortSignal) => () => combined.abort(from.reason);
  for (const signal of signals) {
    if (signal.aborted) {
      combined.abort(signal.reason);
      break;
    }
    signal.addEventListener("abort", abort(signal), { once: true, signal: combined.signal });
  }
  return combined.signal;
}
