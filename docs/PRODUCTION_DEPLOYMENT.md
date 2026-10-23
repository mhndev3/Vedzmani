# Production deployment: decisions and procedure (draft)

Status: **planning document.** Nothing here has been executed against a production host. There is no production
Compose file yet, because it depends on the owner decisions below. Commands are templates; every `<placeholder>` is
an owner-supplied value. See `docs/PRODUCTION_READINESS_AUDIT.md` for the evidence behind each point.

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

Do not "fix" it by disabling `DJANGO_SECURE_SSL_REDIRECT` or by trusting the header from anyone. Pick one:

**A. TLS ends at Nginx** (no TLS-terminating CDN in front, or CDN re-encrypts to origin). Add a `listen 443 ssl`
server with owner-supplied certificate paths and an `80 -> 443` redirect that still answers `/nginx-health`.
`$scheme` is then truthful and the current `prod.py` works unchanged. Open the host firewall for 443 only.

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

## 4. Health checks

`/api/health/` (liveness, no dependencies) is exempt from the HTTPS redirect. The Compose backend check calls
`http://localhost:8000/api/health/`, i.e. `Host: localhost:8000`. Verified under prod settings with
`DJANGO_ALLOWED_HOSTS=<domain>`: that request returns **400**, so a production backend would stay unhealthy and
Nginx (`depends_on: service_healthy`) would not start. In the production Compose file either add `localhost` to
`DJANGO_ALLOWED_HOSTS` (loopback only matters inside the container) or make the check send an allowed `Host` header.
`/api/health/ready/` checks PostgreSQL and Redis and is the right post-deploy gate; responses contain no
configuration or stack traces (errors are logged, not returned).

## 5. Data: PostgreSQL, Redis, backups

- PostgreSQL is the only source of truth (orders, inventory, sessions). Credentials come from environment variables.
  In the base Compose file PostgreSQL is published on host port 5433 (all interfaces); a production topology must not
  publish it, or must bind it to loopback as `docker-compose.vps.yml` does.
- Redis holds only cache and rate-limit counters (`apps/accounts/ratelimit.py`); sessions and OTP challenges are in
  PostgreSQL. Losing Redis resets throttles; it does not lose orders. Persistence is therefore not required by the
  current use cases. Behaviour of the login endpoints while Redis is down has **not** been tested. Redis must not be
  reachable from outside the private network.
- Backups: a dump and restore-into-temporary-database procedure was verified only for the dev VPS
  (`docs/VPS_DEVELOPMENT.md` section 5, not re-run in this session). Backups there live on the same host, so they are
  not disaster recovery. Production needs an off-host destination, a retention period and RPO/RTO (owner decisions)
  and a restore test in a disposable database before launch.
- `docker compose down -v` deletes the named `postgres_data` volume. Never run it on a stack that holds real data.

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
