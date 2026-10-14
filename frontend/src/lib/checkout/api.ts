/**
 * Browser-side client for the Django session API (checkout flow only).
 *
 * - Same-origin requests to /api/... (works behind Nginx, see backend/API.md).
 * - The `sessionid` cookie is HttpOnly: this code never reads or stores it.
 * - Nothing is written to localStorage/sessionStorage.
 * - Unsafe requests send the CSRF token from `GET /api/auth/csrf/` in
 *   `X-CSRFToken` (backend/AUTH.md). The token is fetched fresh per request, so
 *   a rotated token after login can never be stale.
 */

export type ApiDetails = Record<string, { code: string; message: string }[]>;

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; kind: "http"; status: number; code: string; details?: ApiDetails }
  // No usable response (offline, timeout, unreadable body). The outcome of an
  // unsafe request is UNKNOWN in this case: the server may have processed it.
  | { ok: false; kind: "network" };

const TIMEOUT_MS = 20_000;

async function call<T>(path: string, init: RequestInit): Promise<ApiResult<T>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(path, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
      headers: { Accept: "application/json", ...init.headers },
    });
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    if (res.ok) {
      if (body === null) return { ok: false, kind: "network" };
      return { ok: true, status: res.status, data: body as T };
    }
    const err = (body as { error?: { code?: string; details?: ApiDetails } } | null)?.error;
    return {
      ok: false,
      kind: "http",
      status: res.status,
      code: typeof err?.code === "string" ? err.code : "error",
      details: err?.details,
    };
  } catch {
    return { ok: false, kind: "network" };
  } finally {
    clearTimeout(timer);
  }
}

export function apiGet<T>(path: string): Promise<ApiResult<T>> {
  return call<T>(path, { method: "GET" });
}

async function csrfToken(): Promise<string | null> {
  const res = await call<{ csrfToken?: string }>("/api/auth/csrf/", { method: "GET" });
  return res.ok && typeof res.data.csrfToken === "string" ? res.data.csrfToken : null;
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<ApiResult<T>> {
  const token = await csrfToken();
  // No token means nothing was sent: this is a definite failure, not an unknown outcome.
  if (token === null) return { ok: false, kind: "http", status: 0, code: "csrf_unavailable" };
  return call<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify(body),
  });
}
