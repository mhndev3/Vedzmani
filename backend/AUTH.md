# Auth API (phone + OTP, Django session authentication)

Base path: `/api/auth/`. JSON in/out. Session cookie `sessionid` (HttpOnly, SameSite=Lax,
Secure in production). **No tokens in localStorage.** CSRF is enforced on every POST.

## CSRF
1. `GET /api/auth/csrf/` -> `200 {"csrfToken": "..."}` and sets the `csrftoken` cookie.
2. Send the token on every POST as header `X-CSRFToken`. Re-read the `csrftoken` cookie after
   login (Django rotates it on login).

## Endpoints
| Method | Path | Auth | Success |
|---|---|---|---|
| POST | `/otp/request/` `{phone}` | public | `202 {"detail": "OTP request accepted."}` (identical for known/unknown phones) |
| POST | `/otp/verify/` `{phone, code, remember_me?}` | public | `200 {"user": {id, phone, is_staff}, "is_new_user": bool}` + session cookie |
| GET | `/me/` | session | `200 {id, phone, is_staff}`; `401` if anonymous |
| POST | `/logout/` | session | `204`; deletes the server-side session (idempotent) |

`phone` accepts any spelling of an Iranian mobile (`0912...`, `+98912...`, Persian digits...) and is
stored as `+989XXXXXXXXX` (`apps/accounts/phone.py` is the only normalizer).

## Errors
`{"error": {"code": "...", "message": "...", "details": {...}?}}`

| HTTP | code |
|---|---|
| 400 | `validation_error` (`details.phone[].code == "invalid_phone"`), `otp_invalid`, `otp_expired`, `otp_consumed` |
| 401 | `not_authenticated` |
| 403 | `csrf_failed`, `account_disabled` |
| 429 | `rate_limited` (has `Retry-After`), `otp_attempts_exceeded` |
| 503 | `otp_delivery_unavailable` (no SMS provider configured / provider failure) |

## Behavior
- OTP: 6 digits, 5 min TTL, 5 attempts, single use, only the newest code is valid. Stored as
  HMAC-SHA256 (keyed by `SECRET_KEY`, bound to phone+purpose+salt) in PostgreSQL. The code is never in any API response.
- Verify locks the challenge row (`SELECT ... FOR UPDATE`); user creation relies on the UNIQUE phone
  constraint, so concurrent requests cannot double-consume a code or create duplicate users.
- Rate limits (Redis/cache, fixed windows): 60 s resend cooldown + 5/h per phone, 20/h per IP for requests,
  30 per 10 min per IP for verifies. Per-IP limits need `AUTH_TRUSTED_PROXY_COUNT` (=1 behind Nginx).
- `remember_me=false` -> browser-session cookie; `true` -> `AUTH_REMEMBER_ME_SECONDS` (30 days).
- Delivery: `OTP_DELIVERY_BACKEND` (`apps/accounts/delivery.py`). Default **refuses to send** (503);
  `ConsoleDelivery` (dev) / `InMemoryDelivery` (tests) are rejected by production settings.
  To add a real SMS provider: subclass `OTPDelivery`, point the setting at it.
