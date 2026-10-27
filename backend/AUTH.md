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

## Expired-data cleanup (Agent 6, Session 2)
`python manage.py purge_expired_auth_data` (`apps/accounts/cleanup.py`). **Dry run by default**; nothing is deleted without
`--execute`. Output is counts only.

| Table | Eligible rows | Policy |
|---|---|---|
| `django_session` | `expire_date < now` | none needed: Django already refuses these rows and they hold no audit data |
| `accounts_otpchallenge` | `expires_at < now - N days` | **N is an owner decision, there is no default.** Without `--otp-retention-days N` (N >= 1) OTP rows are never touched |

- Consumed, delivery-invalidated and unused challenges follow the same single rule (they are all expired after the TTL).
  A challenge that is still valid, or expired less than N days ago, is never deleted.
- Deleting only EXPIRED rows can neither reopen a guessing window nor allow code reuse: `verify_otp` rejects an expired
  challenge anyway. Visible effect: a code older than the retention answers `otp_invalid` instead of `otp_expired` /
  `otp_consumed`.
- Safe next to live traffic: batches (`--batch-size`, default 1000) use `FOR UPDATE SKIP LOCKED`, so a row that
  `verify_otp` holds locked is skipped and picked up by the next run; one run is bounded by `--max-batches` (default 100).
- Indexes already exist (`otp_expires_at_idx`, Django's `django_session_expire_date`). Measured on a disposable PostgreSQL
  16 with 300k expired rows per table: about 3 s for a 100k+100k run, drained in 3 runs, a 4th run deleted 0.
- Example: `manage.py purge_expired_auth_data --execute --otp-retention-days 30`.

**Scheduling is NOT configured: no branch of this repository contains a scheduler** (no cron, Celery, beat or sidecar; the
production compose file only has one-shot `migrate` services). Until the owner chooses one, nothing runs this command and
expired rows keep accumulating. Options for the owner (each is an infrastructure decision, none was implemented):
1. host cron on the VPS calling `docker compose ... exec -T backend python manage.py purge_expired_auth_data --execute
   --otp-retention-days N` (smallest change, outside the repository);
2. a small compose sidecar that loops the command (needs a compose change);
3. Celery beat (README says Celery is deliberately not introduced yet).

## Client IP and per-IP limits (Agent 6, Session 2)
`get_client_ip` (`ratelimit.py`) with `AUTH_TRUSTED_PROXY_COUNT=1` takes the LAST `X-Forwarded-For` entry. It must be a valid
IP (otherwise the peer address is used); IPv6 collapses to its /64 and IPv4-mapped IPv6 to IPv4. Used only as a rate-limit key.

**Verified locally** (`scripts/proxy-chain-probe/run.ps1`: real `nginx/default.conf` and the infra branch's real
`nginx/prod.conf`, disposable Docker network, fixed client IPs, the real `get_client_ip`; plus `tests/test_accounts_client_ip.py`):
- `nginx/default.conf` appends to `X-Forwarded-For`: a spoofed prefix is kept but ignored, the identity is the address Nginx saw.
- `nginx/prod.conf` overwrites `X-Forwarded-For`; `CF-Connecting-IP` is honored only from addresses listed in
  `cloudflare-realip.conf` (committed empty = honored from nobody) and ignored from any other peer.
- Both configs pass `nginx -t`.

**NOT verified (needs the real VPS / Cloudflare, none was accessed):**
- Which Nginx config and Django settings module vedzmani.ir actually runs, and whether `cloudflare-realip.conf` is populated
  with the current Cloudflare ranges. Without it every user behind a Cloudflare edge address shares ONE per-IP bucket (safe
  against spoofing, but one abuser can exhaust the OTP verify/request budget of everyone on that edge; see the test
  `test_users_behind_one_unresolved_edge_address_share_one_verify_budget`).
- That the backend (gunicorn) is reachable only through Nginx. If anything else can reach it, a request can send its own
  `X-Forwarded-For` and choose its per-IP identity (`test_known_limitation_a_direct_hit_...`). The compose files publish no
  backend port; host firewall and other containers on the network were not checked. The per-phone limit and the
  5-attempts-per-code limit (PostgreSQL) do not depend on the client IP and still bound guessing.
- That the origin only accepts traffic from Cloudflare (otherwise `CF-Connecting-IP` is simply ignored, which is safe).

Evidence the owner can collect without secrets: (1) `nginx -T | grep -E "real_ip|set_real_ip_from"` inside the production Nginx
container shows the Cloudflare ranges; (2) the Nginx access log shows real client addresses, not Cloudflare ones; (3)
`docker compose ps` / `ss -ltn` show no published backend port; (4) the firewall allows 80/443 only as intended.
**Open / production dependencies (not fixed here):**
- Real SMS provider: none chosen. Live delivery verification is **BLOCKED**. No provider environment variables exist;
  a future adapter defines its own and must be isolated behind `OTP_DELIVERY_BACKEND`.
- Cleanup exists as a command but is **not scheduled** and the OTP retention period is undecided (see above).
- Production client-IP chain is **unverified** (see above). `AUTH_TRUSTED_PROXY_COUNT` must keep matching the proxy chain.
- `main`'s Compose still runs `config.settings.dev` (non-Secure cookies, OTP codes and phones logged by `ConsoleDelivery`); the
  production compose with `config.settings.prod` exists only on unmerged infra branches.