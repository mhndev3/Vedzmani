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

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!res.ok) {
    throw new Error(`API ${path} responded ${res.status}`);
  }
  return (await res.json()) as T;
}