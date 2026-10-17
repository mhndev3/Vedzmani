import { BrowserApiError } from "@/lib/browser-api";

/** Dictionary keys (see i18n/dictionaries/auth.ts `errors`) for everything the sign-in API can answer. */
export type AuthErrorKey =
  | "invalid_phone"
  | "invalid_code_format"
  | "otp_invalid"
  | "otp_expired"
  | "otp_consumed"
  | "otp_attempts_exceeded"
  | "rate_limited"
  | "otp_delivery_unavailable"
  | "account_disabled"
  | "csrf"
  | "network"
  | "unexpected"
  | "generic";

export type ClassifiedError = { key: AuthErrorKey; retryAfterSeconds?: number };

const DIRECT: Record<string, AuthErrorKey> = {
  otp_invalid: "otp_invalid",
  otp_expired: "otp_expired",
  otp_consumed: "otp_consumed",
  otp_attempts_exceeded: "otp_attempts_exceeded",
  otp_delivery_unavailable: "otp_delivery_unavailable",
  account_disabled: "account_disabled",
};

export function classifyAuthError(e: unknown): ClassifiedError {
  if (!(e instanceof BrowserApiError)) return { key: "generic" };
  const { status, code, details } = e;

  if (code === "network_error") return { key: status === 0 ? "network" : "unexpected" };
  if (code === "unexpected_response") return { key: "unexpected" };
  if (code === "csrf_unavailable" || code === "csrf_failed") return { key: "csrf" };

  // otp_attempts_exceeded is ALSO a 429: it must not be shown as a generic "slow down".
  if (code in DIRECT) return { key: DIRECT[code] };
  if (status === 429) return { key: "rate_limited", retryAfterSeconds: e.retryAfterSeconds };

  if (status === 400 && code === "validation_error") {
    if (details?.phone?.length) return { key: "invalid_phone" };
    if (details?.code?.length) return { key: "invalid_code_format" };
  }
  return { key: "generic" };
}
