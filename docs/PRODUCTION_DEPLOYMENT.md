# Production deployment: decisions and procedure (draft)

Status: **planning document.** Nothing here was executed against a production host by the authors of this document.
`main` has no production Compose file, because it depends on the owner decisions below. Commands are templates; every
`<placeholder>` is an owner-supplied value. See `docs/PRODUCTION_READINESS_AUDIT.md` for the evidence behind each point.

Revision 2026-10-29: re-checked against `main` at `de13470` (includes PRs #25, #26, #28, #29). **PR #27
(`infra/production-stack-v1`) is an open, unmerged proposal** (production Compose, TLS-terminating Nginx, WhiteNoise,
Cloudflare real-IP tooling), owned by the infrastructure workstream. This document only records contracts that
`main`'s settings impose on it; where it mentions the PR it describes what the PR proposes, not infrastructure that
exists on `main` or is known to run anywhere.

Evidence labels: **[repo]** read in a file at the stated commit; **[test]** asserted by an automated test (local run
and/or CI, as stated); **[owner]** stated by the owner, with no log, output or screenshot in the repository;
**[unverified]** no evidence at all. Nothing in this file is "production-verified": no VPS, Cloudflare, backup or
provider observation was made while writing it.

## 1. Owner decisions that block a production Compose file

| Decision | Why it blocks | Where it lands |
| --- | --- | --- |
| Hosting target and who runs PostgreSQL/Redis | Decides volumes, networks, backups, image registry | Production Compose, section 5 |
| TLS termination (section 2) | Decides Nginx config, `X-Forwarded-Proto` trust, `AUTH_TRUSTED_PROXY_COUNT` | `nginx/`, env |
| Django static-file strategy (section 3) | `/admin/` has no CSS/JS until one exists | Backend image or Nginx |
| Domain, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `NEXT_PUBLIC_API_URL` | Baked into the frontend build and Django checks | `.env` (never committed) |
| Backup destination, retention, RPO/RTO | No backup policy exists for production | Section 5 |
| SMS/OTP provider, payment provider | Customer login and payment do not work without them (`backend/AUTH.md`, `PAYMENT.md`) | Application work, not infrastructure |

## 2. TLS termination: owner decision

Today Nginx listens on port 80 only and always forwards `X-Forwarded-Proto: $scheme`, which is `http` on every
internal hop. `config.settings.prod` trusts that header and redirects every non-health request it sees as `http`.
Verified with Django's test client under prod settings (`backend/tests/test_production_proxy_behavior.py`):
`X-Forwarded-Proto: http` gives `301 https://<host>/...`; `https` is served; the health endpoints are exempt.
Behind a TLS-terminating CDN/WAF that talks plain HTTP to Nginx, this configuration would redirect every page
request to itself. The end-to-end loop has **not** been reproduced (no running edge).

Two related facts pinned by the same tests [test]: Django compares only the **first** comma-separated value of
`X-Forwarded-Proto` with `https`, so the proxy in front of the backend must **overwrite** the header (as
`proxy_set_header X-Forwarded-Proto ...` does) and never append to a client-supplied one; and any value other than
`https` (`HTTPS`, `wss`, `1`, `http, https`) counts as plain HTTP.

Do not "fix" it by disabling `DJANGO_SECURE_SSL_REDIRECT` or by trusting the header from anyone. Pick one:

**A. TLS ends at Nginx** (no TLS-terminating CDN in front, or CDN re-encrypts to origin). Add a `listen 443 ssl`
server with owner-supplied certificate paths and an `80 -> 443` redirect that still answers `/nginx-health`.
`$scheme` is then truthful and the current `prod.py` works unchanged. Open the host firewall for 443 only. PR #27 (open, not merged) proposes this variant (`nginx/prod.conf`, origin
certificate, Cloudflare `Full (strict)`); this document has not verified how it behaves on a real host.

**B. TLS ends at a CDN/WAF; Nginx is reachable only from it.** Nginx must pass `https` only when the request really
came from the edge, otherwise `http`. Template (untested; edge CIDRs come from the provider):

```nginx
geo $realip_remote_addr $vz_from_edge { default 0; <edge-cidr-1> 1; <edge-cidr-2> 1; }
map "$vz_from_edge:$http_x_forwarded_proto" $vz_proto { default http; "1:https" https; }
# in the server block: proxy_set_header X-Forwarded-Proto $vz_proto;
```

Restrict origin access at the host firewall to the edge ranges as well. Per-IP OTP limits then need
`AUTH_TRUSTED_PROXY_COUNT=2` (edge + Nginx) only if the edge appends to `X-Forwarded-For`; check the provider's
behaviour before changing it, because a wrong value lets clients choose their own rate-limit identity.

Keep `DJANGO_HSTS_SECONDS=0` until HTTPS is verified end to end, then raise it in steps.

## 3. Django static files (admin CSS/JS): owner decision

Verified: under prod settings `/static/admin/css/base.css` returns 404, `STATIC_ROOT` does not exist and WhiteNoise is
not installed. Options, smallest change first:

| Option | Change | Trade-off |
| --- | --- | --- |
| WhiteNoise in the backend | New dependency and middleware; `collectstatic` in the image build (needs no database) | Gunicorn serves static files; fine for admin-only assets |
| Shared volume + Nginx `location /static/` | `collectstatic` as a deploy step into a volume mounted read-only in Nginx | No new dependency; one more deploy step to forget |
| Object storage/CDN | `STATIC_URL` points at the CDN; upload on deploy | Depends on the storage vendor decision |

Never run `collectstatic` against an unknown storage target.

## 4. Health checks and the Host contract

Two independent gates apply to every request under `config.settings.prod`. Both are pinned by
`backend/tests/test_production_proxy_behavior.py` (24 cases, run in a subprocess under prod settings with no
database or Redis) [test]:

| Gate | Looks at | Health endpoints |
| --- | --- | --- |
| HTTPS redirect (`SECURE_SSL_REDIRECT`, `SECURE_REDIRECT_EXEMPT = [r"^api/health/"]`) | `X-Forwarded-Proto`, matched on the path | **Exempt**: `/api/health/` and `/api/health/ready/` are never redirected, whatever the header says (also when it is absent). Near-miss paths (`/api/healthz/`) and every other `/api/` path are **not** exempt. |
| `ALLOWED_HOSTS` | `Host` | **Not exempt**: a probe whose Host is not listed (`localhost:8000`, `127.0.0.1:8000`, `backend:8000`) gets **400**, with or without `X-Forwarded-Proto`. The redirect exemption does not help here. |

Consequences for any production topology:

- The development Compose check calls `http://localhost:8000/api/health/`, i.e. `Host: localhost:8000`. Under prod
  settings with `DJANGO_ALLOWED_HOSTS=<domain>` that returns 400, so the backend would stay unhealthy and anything
  with `depends_on: service_healthy` would not start. Two fixes are tested [test]: add `localhost` to
  `DJANGO_ALLOWED_HOSTS` (matching ignores the port), or keep the loopback connection and send
  `Host: <allowed domain>`. Do not disable the redirect or the host check to make a probe pass.
- The Next.js server calls the backend as `http://backend:8000` (`API_INTERNAL_URL`, `docker-compose.yml`) [repo], so
  Django sees `Host: backend:8000`. `backend` must therefore also be in `DJANGO_ALLOWED_HOSTS` (the root
  `.env.example` already lists it) [repo][test].
- PR #27 (open proposal, unmerged) takes the second route for its backend health check and requires `backend` in the
  allowed hosts. That is a statement about the proposal's files; it has not been run against a real host here.
- `/api/health/` is liveness (no dependencies). `/api/health/ready/` checks PostgreSQL and Redis and is the right
  post-deploy gate. Responses contain no configuration or stack traces (errors are logged, not returned).

## 5. Data: PostgreSQL, Redis, backups

- PostgreSQL is the only source of truth (orders, inventory, sessions). Credentials come from environment variables.
  Since PR #25 the base Compose file binds the development database to `127.0.0.1:5433` (loopback) [repo]. A
  production topology should not publish PostgreSQL at all. Docker-published ports bypass UFW, so a host-firewall rule
  alone does not protect a published port.
- Redis holds only cache and rate-limit counters (`apps/accounts/ratelimit.py`); sessions and OTP challenges are in
  PostgreSQL. Losing Redis resets throttles; it does not lose orders. Persistence is therefore not required by the
  current use cases. Per `backend/AUTH.md` (isolated tests) OTP request/verify fail closed with a 5xx while the rate-limit store is down;
  no real Redis outage was exercised. Redis must not be
  reachable from outside the private network.
- Backups: a dump and restore-into-temporary-database procedure was verified only for the dev VPS
  (`docs/VPS_DEVELOPMENT.md` section 5, not re-run in this session). Backups there live on the same host, so they are
  not disaster recovery. Production needs an off-host destination, a retention period and RPO/RTO (owner decisions)
  and a restore test in a disposable database before launch.
- `docker compose down -v` deletes the named `postgres_data` volume. Never run it on a stack that holds real data.
- `manage.py purge_expired_auth_data` (PR #29, merged) is dry-run by default and **not scheduled anywhere**; expired
  sessions and OTP rows accumulate until the owner picks a scheduler and an OTP retention period (`backend/AUTH.md`).

## 6. Release procedure (template, not yet executed)

1. Pre-checks on the release commit: CI green (backend, frontend, E2E); `python manage.py check --deploy
   --fail-level WARNING` under `config.settings.prod`; `makemigrations --check --dry-run`.
2. Take a backup and confirm it exists and is non-empty **before** touching the schema. Record its location.
3. Build images from the release commit. Pin the commit SHA in the image tag; do not deploy `latest`.
4. Show the plan: `python manage.py migrate --plan` in a one-off backend container. Review for long locks or
   data-rewriting operations.
5. Apply: `python manage.py migrate` in a one-off container, **once**, before starting the new backend replicas.
   Do not run migrations from every container's start command.
6. Static files: run the strategy chosen in section 3.
7. Start backend, then frontend, then Nginx. Gate on `/api/health/ready/` returning 200 through the public hostname.
8. Smoke test: storefront loads, `/admin/` has styling, an order can be listed. Customer sign-in cannot be verified
   until an SMS provider exists.

Rollback limits: application images can be rolled back by tag; applied migrations are not automatically reversible.
If a migration changed data or dropped columns, the rollback is a restore from the step-2 backup (accepting loss of
writes made since). Never delete or rewrite migration files, and do not use `migrate <app> zero` on production.

## 7. Reproducibility notes

Base images (`python:3.13-slim`, `node:24-alpine`, `postgres:16-alpine`, `redis:7-alpine`, `nginx:1.27-alpine`) are
tags, not digests, and `backend/requirements/base.txt` uses version ranges without a lock file, so two builds of the
same commit can differ. The frontend uses `pnpm-lock.yaml` with `--frozen-lockfile`. Pinning digests and generating a
backend lock file are worthwhile before launch but need a compatibility run, so they are tracked in the audit and not
changed here.

## 8. Release gates (all open)

Production launch is blocked until every gate below is closed with evidence of the kind in the last column. "Evidence
today" is what exists at `de13470` plus this branch; nothing was observed on a VPS, in Cloudflare, at a provider or in
a backup store while preparing this revision. Items marked **[owner]** come from statements recorded in the open PR #27
documentation, which this revision could not confirm.

| # | Gate | Evidence today | Closes when |
| --- | --- | --- | --- |
| 1 | Real SMS provider and end-to-end OTP test | **[repo]** no provider; production returns `503 otp_delivery_unavailable`; `prod.py` refuses console/in-memory OTP backends. **[test]** failure handling with mocked delivery. Live delivery: **blocked**. | Provider chosen, adapter behind `OTP_DELIVERY_BACKEND`, a real phone completes request, verify and login on a production-like stack; send failures observed. |
| 2 | Payment integration and unpaid-order behavior | **[repo]** no payment provider (`backend/PAYMENT.md`); every order is `unpaid` and nothing changes that; no cancellation or stock restoration for unpaid orders. | Provider chosen and integrated with verified callbacks, idempotent processing and the owner's unpaid-order policy implemented and tested (or an explicit owner decision that V1 has no online payment, with the order flow stated honestly in the UI). |
| 3 | Verified Cloudflare real-IP / trusted-proxy chain | **[repo]** `main`'s `nginx/default.conf` appends to `X-Forwarded-For` and does not restore client IPs. **[test]** `get_client_ip` and the local Nginx probe (`scripts/proxy-chain-probe`, PR #29). PR #27 proposes `nginx/prod.conf` (overwrites `X-Forwarded-For`, real-IP include committed empty). **[owner]** a populated server-local file was reported, unconfirmed. **[unverified]** the access log on the host, the value of `AUTH_TRUSTED_PROXY_COUNT` in production, whether the backend is reachable other than through Nginx. | Owner-collected evidence (`nginx -T` real-IP directives, an access-log line with a real client address, no published backend port) matching the chain assumed by `AUTH_TRUSTED_PROXY_COUNT`; until then all users behind one edge address share one per-IP bucket. |
| 4 | Origin firewall with safe rollback | **[repo]** Compose comments state Docker-published ports bypass UFW; the proposed stack publishes 80/443 on all interfaces. **[unverified]** actual firewall state. | Only Cloudflare ranges (plus owner SSH) reach 80/443, enforced where Docker traffic is filtered, applied with a scheduled automatic revert and provider-console access, then tested from outside. |
| 5 | Valid origin TLS and verified Full (strict) | **[owner]** a temporary self-signed certificate and Cloudflare mode `Full` were reported, so `Full (strict)` is not in effect. **[unverified]** both, as they cannot be read from the repository. | A valid origin certificate (Cloudflare Origin CA or public) installed and checked with SNI, **then** the mode switched to `Full (strict)` and HTTPS verified through the edge. Never switch first. |
| 6 | Off-host automated backups and a successful restore rehearsal | **[repo]** none; the dev VPS dump/restore procedure (`docs/VPS_DEVELOPMENT.md`) keeps files on the same host and was not re-run here. **[unverified]** anything else. | Off-host destination, schedule, retention and RPO/RTO decided; a restore into a disposable database passes row-count and application checks; evidence (date, size, result) recorded. |
| 7 | Safe deployment, migration and rollback procedure | **[repo]** the template in section 6 and the proposal in PR #27; neither has been rehearsed. | Rehearsed on a non-production copy: backup first, `migrate --plan` reviewed, one-shot migrate, image rollback by SHA, data rollback by restore; result recorded. |
| 8 | Production health and smoke tests | **[test]** the health/redirect/host contract (this module; local run 2026-10-29, CI on push). **[repo]** PR #27 proposes an offline validator. **[unverified]** any result from a production host. | `/api/health/ready/` returns 200 through the public hostname; storefront and styled `/admin/` load; real OTP sign-in and an order succeed; results recorded with date and method. |

Related owner decisions that are not gates but block parts of the above: scheduler for `purge_expired_auth_data` and
the OTP retention period; Django static-file strategy (section 3; PR #27 proposes WhiteNoise); `DJANGO_HSTS_SECONDS`
stays 0 until HTTPS is verified end to end.
