# Production readiness audit (Agent 16, session 1)

Date: 2026-10-18. Audited commit: `c16f54eb5123a4db5d702f1c7d1298087cc4bbfc` (`origin/main`, PR #22 merged, no open PRs).
Scope: repository inspection plus checks that need no production access. Nothing was deployed, no real database was
touched, no Docker stack was started. **This document does not declare the project production-ready.**

Status labels: **confirmed** = shown by a command run in this session or by reading the cited file;
**not reproduced** = derived from the cited files, no running stack was available to exercise it.

## Findings

### P0 - critical

None found. Limits of that statement: no tracked `.env` file (only the three `.env.example` files), no `.env`, `.pem`
or `.key` path in any commit reachable from any ref, and a pattern scan of tracked files (AWS key IDs, PEM private-key
headers, GitHub and `sk-` style tokens) matched nothing. This is not a full secret scanner and does not cover secrets
already pasted into chats or CI settings.

### P1 - release blockers

| # | Finding | Evidence | Status |
| --- | --- | --- | --- |
| 1 | **No production topology exists.** The only Compose file hard-codes development settings, so any deployment built from the repository runs `config.settings.dev` (dev OTP console delivery, dev defaults). `docker-compose.vps.yml` is a development overlay. | `docker-compose.yml:33` `DJANGO_SETTINGS_MODULE: config.settings.dev`; `docs/VPS_DEVELOPMENT.md` "Development only"; no production override or deploy workflow under `.github/workflows` (only `ci.yml`, `e2e.yml`) | confirmed. Needs owner hosting decision. Not fixed. |
| 2 | **No `migrate` or `collectstatic` step anywhere in a deploy path, and nothing serves Django static files.** `/admin/` would load without CSS/JS. | `backend/Dockerfile` `CMD` is only gunicorn; `base.py:122-123` sets `STATIC_URL`/`STATIC_ROOT`; no WhiteNoise in `requirements/base.txt`; `nginx/default.conf` has no `/static/` location; `README.md` "Production direction" already says admin static serving is not done | confirmed. Strategy (WhiteNoise vs. shared volume + Nginx vs. CDN) is a topology decision. Not fixed. |
| 3 | **Probable redirect loop behind a TLS-terminating edge.** Nginx listens on 80 only and always sends `X-Forwarded-Proto $scheme` (= `http`). Production settings redirect every request that Django sees as non-HTTPS (`SECURE_SSL_REDIRECT` defaults to true; only `^api/health/` is exempt). With CDN/WAF -> Nginx (the documented direction), Django would answer 301 to `https://` for every page. | `nginx/default.conf` (`proxy_set_header X-Forwarded-Proto $scheme;`); `prod.py:22-24`. Probe run here: with prod settings, Django's `SecurityMiddleware` returns `301 https://...` for `X-Forwarded-Proto: http` and passes `https` through. | Django half confirmed; end-to-end loop **not reproduced**. Fix depends on who terminates TLS (trusted-header `map` in Nginx, or TLS at Nginx). Not fixed. |
| 4 | **Customer login and payment cannot work in production.** No SMS provider: production default `UnconfiguredDelivery` refuses (503) by design; no payment provider. | `base.py:159-160`; `backend/AUTH.md`, `backend/PAYMENT.md`; `PROJECT_CONTROL.md` pending decisions | confirmed, documented. Owner decisions. Not fixed. |

### P2 - important

| # | Finding | Evidence | Status |
| --- | --- | --- | --- |
| 5 | Production settings accepted the placeholder key shipped in `.env.example` (`change-me`) and any short key. | Probe before the fix: prod settings loaded with a 9-character `change-me` key (`SECRET_KEY` guard only rejected the `dev-only` prefix). | **Fixed**: `prod.py` now refuses known placeholders and keys under 32 characters (key never echoed). Tests: `test_production_refuses_to_boot_with_placeholder_or_short_secret_key` (5 cases). |
| 6 | CI never exercised the production settings module or Django's deployment check. | `.github/workflows/ci.yml` ran `check` under `config.settings.test` only. | **Fixed**: backend job now runs `check --deploy --fail-level WARNING` under `config.settings.prod` with throwaway values, no database contact. Locally exit 0 with the CI values; exit 1 without the CI-only HSTS values (W004). Not yet run on GitHub Actions. |
| 7 | README claimed "Only Nginx publishes a host port"; the base Compose file also publishes PostgreSQL on host port 5433 on all interfaces, and Docker-published ports bypass UFW. | `docker compose config` resolved ports: base = nginx `:8080`, postgres `:5433` (no host IP); base+vps = both on `127.0.0.1`. | **Fixed** (README corrected). The base file itself is unchanged; the VPS overlay remains the mitigation. |
| 8 | Backend container health check uses `http://localhost:8000/api/health/` (Host `localhost:8000`). With production `DJANGO_ALLOWED_HOSTS` set to the real domain only, Django would answer 400, the backend would stay unhealthy and Nginx (`depends_on: service_healthy`) would not start. | `docker-compose.yml:48`; `prod.py:10-11` | **not reproduced**. Belongs with the production Compose work (include `localhost` in allowed hosts or send a `Host` header). Not fixed. |
| 9 | No production backup/retention/restore policy. A tested dump and restore-into-temp-database procedure exists for the dev VPS only; off-server backup is not configured. | `docs/VPS_DEVELOPMENT.md` section 5 and 9 (previous-session verification, not re-executed here) | Needs owner hosting/DB decision. Not fixed. |

### P3 - improvements

- Nginx has no TLS server block, no explicit proxy timeouts (defaults), no rate limiting; `client_max_body_size 10m` is set.
- `AUTH_TRUSTED_PROXY_COUNT=1` assumes Nginx is the only proxy. Behind a CDN the rightmost `X-Forwarded-For` entry is the CDN, so per-IP OTP limits would group users by CDN edge; revisit with the real topology.
- No Content-Security-Policy; HSTS is intentionally `0` until HTTPS is verified (`prod.py:32`). Next.js sets nosniff, frame, referrer and permissions headers only.
- Base images are tags, not digests (`python:3.13-slim`, `node:24-alpine`, `postgres:16-alpine`, `redis:7-alpine`, `nginx:1.27-alpine`); backend requirements are version ranges without a lock file, so image builds are not reproducible.
- Gunicorn runs with defaults apart from 3 workers (30 s default timeout); no tuning documented.
- `postgres_data` is a named volume and `down -v` deletes it. The warning exists in `docs/VPS_DEVELOPMENT.md` but not in the README or Compose file.
- E2E destructive helpers refuse to run without `E2E_THROWAWAY_DB=1` and a dev/test settings module. The flag is an operator confirmation, not proof of database identity (the code and VPS doc say so). CI E2E uses a fresh runner and `down -v` on its own project only. E2E is not a required check.
- Frontend: `NEXT_PUBLIC_API_URL` is the only build argument; `API_INTERNAL_URL` is server-side. A scan of the built client bundle for private values was **not run**.
- Object storage is correctly described as a future boundary (`MEDIA_CDN_BASE_URL` only; no storage credentials in settings). Upload handling was not audited because no upload endpoint was reviewed.

## Verification record (2026-10-18, Windows host, Python 3.14.6 in `backend/.venv`, Node 24.15.0, pnpm 11.20.0)

| Check | Result |
| --- | --- |
| `git fetch --prune origin` | exit 0; `origin/main` = `c16f54e` |
| GitHub pull requests page | 0 open, 22 closed |
| `manage.py check` (`config.settings.test`) | exit 0, no issues |
| `manage.py check --deploy` (`config.settings.prod`, throwaway env, before fix) | exit 0, one warning: `security.W004` (HSTS deferred by design) |
| `manage.py check --deploy --fail-level WARNING` with the exact CI step values | exit 0, no issues |
| Same without the CI HSTS values | exit 1 (`security.W004`) |
| Prod settings with `ConsoleDelivery` | exit 1 `ImproperlyConfigured` (guard works) |
| `wsgi.py` default settings module | `config.settings.prod` |
| `pytest tests/test_accounts_security.py -k production` (DATABASE_URL pointed at an unreachable port on purpose) | 8 passed (3 existing + 5 new), exit 0 |
| `docker compose config --quiet` base, and base + vps (dummy env file in TEMP) | exit 0 both |
| `pnpm lint`, `pnpm typecheck`, `pnpm build` in `frontend/` | exit 0 each |

**BLOCKED:** full backend `pytest` and `makemigrations --check`: the Docker daemon is not running (starting it could auto-start other projects' containers), and the only PostgreSQL reachable is a persistent host install on port 5432 whose owner, data and credentials are unknown, so it was deliberately not used. Docker image builds and Compose stack start: same reason.
**NOT RUN:** Playwright E2E (needs a throwaway stack), the new CI step on GitHub Actions, client-bundle secret scan, any live-system scan.

## Remaining external decisions

Hosting provider and TLS termination point; static-file strategy; SMS/OTP provider; payment provider; object storage/CDN vendor; production PostgreSQL/Redis and backup/retention policy; owner rotation of any credential ever pasted into chats (none found in the repository).

## Update: Agent 17, session 1 (2026-10-18)

Audited commit: `c9001108656844658486b41b54447f7322588547` (`origin/main`, merge of PR #23). Scope as above: no
deployment, no real database, no Docker stack. The deployment plan and options are in `docs/PRODUCTION_DEPLOYMENT.md`.
**This update does not declare the project production-ready.**

| Finding | Status now | Evidence from this session |
| --- | --- | --- |
| P1-1 no production topology | Still open (owner decision) | `docker-compose.yml` still sets `config.settings.dev`; no other Compose file besides the dev VPS overlay |
| P1-2 admin static files | **Now confirmed under prod settings** | `GET /static/admin/css/base.css` with HTTPS forwarded returns 404; `STATIC_ROOT` absent; no WhiteNoise |
| P1-3 redirect loop | Django half now covered by tests; end-to-end still **not reproduced** | `backend/tests/test_production_proxy_behavior.py`; options A/B in `PRODUCTION_DEPLOYMENT.md` section 2 |
| P1-4 SMS/payment | Still open (owner decision) | Unchanged |
| P2-5 placeholder secret key | Resolved by PR #23 | Guard and tests merged |
| P2-6 `check --deploy` in CI | **Now verified on GitHub Actions** | CI runs #89 (`bb85481`), #90 (PR #23) and #91 (`c900110`) completed successfully; E2E #8 and #9 as well. Step-level logs were not opened |
| P2-8 health check Host vs `ALLOWED_HOSTS` | **Now confirmed** | Under prod settings with `DJANGO_ALLOWED_HOSTS` = one domain, `Host: localhost:8000` returns 400; an allowed host returns 200 |
| P2-9 backups | Still open (owner decision) | Dev-only procedure; off-host destination, retention, RPO/RTO undefined |

New observations (no P0/P1): Redis stores only rate-limit counters, so persistence is not required (section 5 of the
deployment doc); the backend and frontend containers already run as non-root users; `.dockerignore` files exclude
`.env*`; no secret values were found or printed. Unchanged P3 items: image digests, backend lock file, Gunicorn tuning,
no restart policy in the base Compose file.

Changed in this session: a documentation file, this update, and one test module pinning the proxy/redirect contract.
No settings, Compose, Nginx or Dockerfile change: each remaining fix depends on an owner decision.

## Update: Agent 6 continuation, session 2 (2026-10-29)

Re-checked against `main` at `de13470` (merges of PRs #25, #26, #28, #29 since the audit above). Scope unchanged: no
deployment, no VPS or Cloudflare access, no database. **This update does not declare the project production-ready.**
The release gates are listed with their evidence in `docs/PRODUCTION_DEPLOYMENT.md` section 8; evidence labels are
defined at the top of that file.

| Item | Change since the 2026-10-18 update | Evidence |
| --- | --- | --- |
| P2-8 health check vs `ALLOWED_HOSTS` | Contract now fully pinned: the HTTPS-redirect exemption covers `/api/health/` and `/api/health/ready/` only; `ALLOWED_HOSTS` is not exempt (400 for `localhost`, `127.0.0.1`, `backend` unless listed); both remediations pass. The earlier version of the test probe took no `Host` argument, so the Host-dependent cases could not be expressed; fixed. | [test] `backend/tests/test_production_proxy_behavior.py`, run locally 2026-10-29 |
| P1-3 redirect loop | Still open (owner decision). New: only the first `X-Forwarded-Proto` value counts, so the proxy must overwrite the header. PR #27 (open) proposes TLS at Nginx, which would make `$scheme` truthful. | [test]; the proposal is [repo] on an unmerged branch |
| Postgres exposure | `docker-compose.yml` now binds `127.0.0.1:5433` (PR #25). Earlier statement that the base file publishes it on all interfaces is obsolete. | [repo] |
| Client-IP / rate-limit chain | `get_client_ip` hardened (valid IP required, IPv6 /64) and locally probed (PR #29). Production chain still unverified. | [test] local only; production [unverified] |
| Auth data retention | `purge_expired_auth_data` exists but is not scheduled; OTP retention undecided. | [repo] |
| Admin login | Admin now requires the staff password (OTP-only sessions refused); Nginx throttles `POST /admin/login/`. | [test] / [repo] |
| P1-1, P1-2, P1-4, P2-9 | Unchanged on `main`. PR #27 (open) proposes a production Compose stack and WhiteNoise; none of it is merged or confirmed running. | [repo] on an unmerged branch |

CI for this branch has not run on the new commits at the time of writing; the earlier CI statements (runs #89 to #91,
E2E #8 and #9) concern the 2026-10-18 audit commit and are unchanged. No VPS, Cloudflare or backup observation is
claimed anywhere in this update.
