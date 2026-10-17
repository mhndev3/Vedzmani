/**
 * Where the customer goes after signing in.
 *
 * `?next=` comes from the URL, so it is attacker-controlled. Only a same-origin,
 * locale-prefixed path is honoured; anything else (absolute URL, `//host`, `\host`,
 * `javascript:`, control characters, the sign-in page itself) falls back to the default.
 * The path is re-prefixed with the CURRENT locale.
 *
 * Pure on purpose (relative import, no alias): unit-tested directly by e2e/tests/auth-redirect.spec.ts.
 */
import { isLocale, type Locale } from "../../i18n/config";

const PLACEHOLDER_ORIGIN = "http://sign-in.invalid";
const MAX_LENGTH = 512;

export function defaultDestination(locale: Locale): string {
  return `/${locale}/profile`;
}

export function safeRedirectPath(next: unknown, locale: Locale): string {
  const fallback = defaultDestination(locale);
  const raw = Array.isArray(next) ? next[0] : next;
  if (typeof raw !== "string" || raw.length === 0 || raw.length > MAX_LENGTH) return fallback;
  // URL parsers strip tabs/newlines (`/\t/evil.com` -> `//evil.com`): reject them outright.
  if (/[\u0000-\u001f\u007f\s]/.test(raw)) return fallback;
  if (!raw.startsWith("/")) return fallback;

  let url: URL;
  try {
    url = new URL(raw, PLACEHOLDER_ORIGIN);
  } catch {
    return fallback;
  }
  // `//evil.com` and `/\evil.com` resolve to another origin here.
  if (url.origin !== PLACEHOLDER_ORIGIN) return fallback;

  const [, first = "", ...rest] = url.pathname.split("/");
  if (!isLocale(first)) return fallback;
  const path = rest.length > 0 ? `/${rest.join("/")}` : "";
  if (path === "/sign-in" || path.startsWith("/sign-in/")) return fallback;

  return `/${locale}${path}${url.search}`;
}

/** Link to the sign-in page that returns the customer to `next` afterwards. */
export function signInHref(locale: Locale, next: string): string {
  return `/${locale}/sign-in?next=${encodeURIComponent(next)}`;
}
