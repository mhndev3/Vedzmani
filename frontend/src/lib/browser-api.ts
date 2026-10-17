/**
 * Browser-side transport for the Django API (session cookie + CSRF), see backend/AUTH.md and API.md.
 * Same-origin only: calls go to relative `/api/...` URLs, which exist behind Nginx (compose topology).
 * The `sessionid` cookie is HttpOnly and never touched here; nothing is stored in web storage.
 * It transports requests and parses the error envelope; it contains no business logic.
 */

export type ErrorDetails = Record<string, { code?: string; message?: string }[]>;

export class BrowserApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly details?: ErrorDetails,
    /** Seconds from the `Retry-After` header (Django sends it on 429), when present and numeric. */
    public readonly retryAfterSeconds?: number,
  ) {
    super(`API ${status} ${code}`);
    this.name = "BrowserApiError";
  }
}

const TIMEOUT_MS = 20_000;

function retryAfterSeconds(res: Response): number | undefined {
  const seconds = Number(res.headers.get("Retry-After"));
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : undefined;
}

async function parseError(res: Response): Promise<BrowserApiError> {
  const retryAfter = retryAfterSeconds(res);
  try {
    const body = (await res.json()) as { error?: { code?: string; details?: ErrorDetails } };
    return new BrowserApiError(res.status, body.error?.code ?? "error", body.error?.details, retryAfter);
  } catch {
    return new BrowserApiError(res.status, "error", undefined, retryAfter);
  }
}

async function send(path: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(path, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
      headers: { Accept: "application/json", ...init.headers },
    });
  } catch {
    throw new BrowserApiError(0, "network_error");
  } finally {
    clearTimeout(timer);
  }
}

/** A fresh token per unsafe request, so a token rotated by login can never be stale. */
async function csrfToken(): Promise<string> {
  const res = await send("/api/auth/csrf/", { method: "GET" });
  if (!res.ok) throw await parseError(res);
  const body = (await res.json().catch(() => null)) as { csrfToken?: string } | null;
  if (!body?.csrfToken) throw new BrowserApiError(res.status, "csrf_unavailable");
  return body.csrfToken;
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

export async function apiRequest<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRFToken"] = await csrfToken();

  const res = await send(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw await parseError(res);
  try {
    return (res.status === 204 ? undefined : await res.json()) as T;
  } catch {
    throw new BrowserApiError(res.status, "network_error");
  }
}

/**
 * Dictionary key for an error: the first field-level code of a validation error
 * (e.g. `max_quantity`, `unavailable`) wins over the generic `validation_error`.
 */
export function errorKey(e: unknown): string {
  if (!(e instanceof BrowserApiError)) return "generic";
  if (e.code === "validation_error" && e.details) {
    const first = Object.values(e.details)[0]?.[0]?.code;
    if (first) return first;
  }
  return e.code;
}

export function errorText(messages: Record<string, string>, e: unknown): string {
  return messages[errorKey(e)] ?? messages.generic;
}
