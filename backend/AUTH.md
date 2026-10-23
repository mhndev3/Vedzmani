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

## OTP: development vs production (Agent 11 audit)
- **Production login does not work yet.** No SMS provider is selected, configured or tested. With the default
  `UnconfiguredDelivery`, `POST /otp/request/` answers `503 otp_delivery_unavailable`, so no real customer can sign in.
  Do not describe production login as working until a provider is chosen, configured and verified end to end.
- `ConsoleDelivery` is **development only**: it writes the code to the server log (logger `apps.accounts.delivery`,
  level WARNING). It is not SMS delivery. `InMemoryDelivery` is for tests. `config.settings.prod` refuses to boot with
  either.
- **Docker Compose runs the backend with `DJANGO_SETTINGS_MODULE=config.settings.dev`** (see `docker-compose.yml`), and
  the dev settings default `OTP_DELIVERY_BACKEND` to `ConsoleDelivery`. In that topology OTP codes are written to the
  backend's log (whether they appear in `docker compose logs` depends on the logging configuration, which was not
  verified). Treat Compose as a development/staging topology, never as a production deployment. Setting
  `OTP_DELIVERY_BACKEND=apps.accounts.delivery.UnconfiguredDelivery` in Compose makes it refuse to send, like production.
- The compose topology was only inspected, not changed or run.


## Audit (Agent 6, Session 1)
Verified against the code and isolated tests (disposable PostgreSQL, in-memory cache, mocked delivery). Nothing here
was verified against a real SMS provider or a production environment.

**Mechanism:** phone + OTP, Django DB-backed session auth, CSRF enforced on every POST (auth POSTs re-apply
`csrf_protect`; other endpoints use `SessionAuthentication401`). No tokens, no passwords for customers.

**Admin gate:** an OTP-established session is flagged (`OTP_SESSION_FLAG`) and refused by `/admin/` (see `ADMIN.md`).
Before this change an OTP-only session for any `is_staff` phone opened the admin, bypassing the staff password.
The customer API is unaffected.

**Delivery failures:** any exception raised by a delivery adapter (not only `OTPDeliveryError`) yields `503
otp_delivery_unavailable`, expires the unsent code and logs only the exception type (provider messages may embed API
keys or phone numbers). Adapters should still raise `OTPDeliveryError`.

**Session lifetime (effective behavior):**
| Login | Cookie | Server-side row |
|---|---|---|
| `remember_me=false` | no expiry (dropped at browser close) | **`SESSION_COOKIE_AGE` = 14 days** (a stolen cookie works that long) |
| `remember_me=true` | `AUTH_REMEMBER_ME_SECONDS` (30 days) | same 30 days, not sliding |
Expired rows are rejected (401). Logout deletes the row. The session key is rotated at login.

**Cookies:** `sessionid` HttpOnly + SameSite=Lax everywhere; `Secure` only under `config.settings.prod`
(`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) so local HTTP development keeps working. Behind Nginx, prod trusts
`X-Forwarded-Proto` (`SECURE_PROXY_SSL_HEADER`); the proxy must set it.

**Abuse limits:** per phone 60 s cooldown + 5 requests/h; per IP 20 requests/h and 30 verifies/10 min; 5 attempts per
code. A new code resets the attempt counter, so guessing is bounded by 5 x 5 = **25 wrong guesses per phone per hour**
regardless of the number of IPs. Side effect: anyone can use up a victim's 5 code requests per hour (no way around
this without per-account identity).

**Privacy:** request answers are identical for known/unknown phones; a wrong code answers `otp_invalid` for known,
unknown and never-requested phones alike; `account_disabled` is only returned after a correct code; errors never echo
the phone or code.

**Rate-limit store down (Redis):** OTP request and verify fail closed (HTTP 5xx, nothing created or sent, no login,
no internals in the body). Sessions and OTP state stay in PostgreSQL.

**Open / production dependencies (not fixed here):**
- Real SMS provider: none chosen. Live delivery verification is **BLOCKED**. No provider environment variables exist;
  a future adapter defines its own and must be isolated behind `OTP_DELIVERY_BACKEND`.
- Nothing purges expired `django_session` rows (schedule `manage.py clearsessions`) or `OTPChallenge` rows (they hold
  phone numbers and are kept forever). No scheduler exists in the repo.
- Per-IP limits need the real client IP: `AUTH_TRUSTED_PROXY_COUNT` must match the proxy chain (Nginx = 1; behind
  Cloudflare the Nginx real-IP configuration decides). Not verifiable without a deployment.
- Compose still runs `config.settings.dev` (non-Secure cookies, console OTP delivery).