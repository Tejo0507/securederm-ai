const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const CSRF_COOKIE_NAME = "csrf_token";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const REQUEST_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 120_000;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1")}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();

  const headers: Record<string, string> = {
    ...(options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string>),
  };

  // The session lives in an httpOnly cookie the browser attaches
  // automatically (credentials: "include"); state-changing requests also
  // echo back the CSRF cookie's value in a header the backend verifies.
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = getCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken;
  }

  // Without a timeout a hung backend leaves every page on "Loading..." forever.
  // Uploads get longer since they legitimately move a lot of data.
  const timeoutMs = options.body instanceof FormData ? UPLOAD_TIMEOUT_MS : REQUEST_TIMEOUT_MS;
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), timeoutMs);
  const signal = options.signal
    ? AbortSignal.any([options.signal, timeout.signal])
    : timeout.signal;

  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...options,
      headers,
      credentials: "include",
      signal,
    });
  } catch (err) {
    if (options.signal?.aborted) throw err; // caller cancelled on purpose
    // Browsers surface network failures as an opaque TypeError("Failed to fetch").
    throw new ApiError(
      0,
      timeout.signal.aborted
        ? "The server took too long to respond."
        : "Cannot reach the server. Is the backend running?",
    );
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    // `detail` is only a string for errors we raise ourselves; guard against
    // other shapes so the UI never renders "[object Object]".
    const detail = typeof err?.detail === "string" ? err.detail : "Request failed";
    throw new ApiError(res.status, detail || "Request failed");
  }

  // 204 / empty bodies are valid successes and would make res.json() throw.
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
