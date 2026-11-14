import "server-only";

/**
 * Minimal server-side fetch helper for the Django/DRF API.
 * Django owns all business logic; this only transports requests.
 * Never import from a Client Component (browser code uses NEXT_PUBLIC_API_URL).
 */
const API_BASE =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";
const API_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  constructor(
    public readonly path: string,
    public readonly status: number,
  ) {
    super(status === 0 ? `API ${path} timed out or could not be reached` : `API ${path} responded ${status}`);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(API_TIMEOUT_MS);
  const signal = init?.signal
    ? AbortSignal.any([init.signal, timeoutSignal])
    : timeoutSignal;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      signal,
      headers: {
        Accept: "application/json",
        // Production TLS terminates at Nginx; Django needs the original scheme
        // to avoid redirecting internal HTTP requests back to HTTPS.
        "X-Forwarded-Proto": "https",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(path, 0);
  }

  if (!res.ok) {
    throw new ApiError(path, res.status);
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError(path, 502);
  }
}
