# Security review, Agent 8 session 1

Reviewed commit: `c9001108656844658486b41b54447f7322588547` (`origin/main`, 2026-10-19). Local code and configuration
review only. No VPS, production, DNS, CDN or live service was touched. **This is not a full security audit and does not
declare the application secure.** It complements `docs/PRODUCTION_READINESS_AUDIT.md` (not repeated here).

Status: **confirmed** = shown by a command run in this session or by reading the cited file; **potential** = plausible
but not demonstrated.

## Fixed in this branch

| # | Severity | Finding | Evidence | Fix |
| --- | --- | --- | --- | --- |
| 1 | Medium | Base Compose published PostgreSQL on every host interface (`5433:5432`). Docker-published ports bypass UFW, and the stack is run on a VPS. Confirmed. | `docker compose config` before: `postgres host_ip=` (empty = all interfaces). | `docker-compose.yml` binds `127.0.0.1:5433:5432`. After: base and base+vps both `127.0.0.1`. README and overlay comment corrected. |
| 2 | Medium | Django Admin password login (staff only; customers use OTP) had no brute-force throttle, and `/admin/` is proxied publicly. Confirmed from `nginx/default.conf`. | Real nginx 1.27 container: 10 POSTs to `/admin/login/` gave 6 pass-through then 4x `429`; GET and other paths never limited. | `limit_req` on `POST /admin/login/` only (10 req/min/address, burst 5). Key is the address Nginx sees: behind a CDN it is the edge address until real client IP restoration is configured. |

Guard tests: `backend/tests/test_deploy_config_security.py` (3 static checks).

## Not fixed: owned by Agent 7 (Django Admin) - do not duplicate

- **Stock `GroupAdmin` is registered with no override** (confirmed: `Group in admin.site._registry` is `True`,
  `django.contrib.auth.admin.GroupAdmin`). A staff user with `auth.change_group` can add any permission to a group they
  belong to. Confirmed by registry probe; exploit not run.
- **`UserAdmin` leaves `is_staff` and `is_active` editable for non-superusers** and allows password change of any
  non-superuser account for users holding `accounts.change_user`. `groups`, `user_permissions` and `is_superuser` are
  already read-only for non-superusers (`accounts/admin.py`). Potential escalation path; needs Agent 7's decision.
- Cart phone-search privacy: reported by Agent 7, not re-verified here.
- At review time Agent 7's worktree had no commits and no pushed branch, only untracked test files.

## Not fixed: other owners or decisions

- Frontend `next.config.ts` (and `Dockerfile`, `.env.example`) are being modified in Agent 2's uncommitted worktree, so
  no frontend header change was made here. No CSP exists (inline scripts/styles make a safe policy a separate task).
- Nginx: no TLS block and no rate limiting on `/api/auth/*`. Application-level OTP limits exist and are sound
  (`accounts/ratelimit.py`); per-address Nginx limits depend on the final CDN/proxy topology.
- Dependencies: `pip-audit` of the installed venv found only `pytest 8.4.2` (PYSEC-2026-1845, dev-only, fix needs
  pytest 9, a major upgrade). `pnpm audit --prod` clean; full `pnpm audit` reports one high advisory for
  `braces <=3.0.3` via `eslint-config-next` (lint tooling, not in the runtime image). Requirements are ranges without a
  lock file, so image builds may resolve different versions than the audited venv.

## Reviewed, no issue found

Production settings composition (DEBUG, ALLOWED_HOSTS, secret guards, secure cookies, proxy header, CORS closed by
default, `check --deploy` clean); OTP flow (HMAC-hashed codes, constant-time compare, attempt counter in PostgreSQL,
session rotation on login, CSRF on login); cart/order ownership (always `request.user`, other users' orders 404);
no upload endpoints exist; Next.js `?next=` redirect validator; no secrets in `NEXT_PUBLIC_*`; backend and frontend
images run as non-root users.
