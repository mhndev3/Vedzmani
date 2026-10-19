# Production infrastructure (Agent 1, session 1)

Status: prepared for review. **Nothing in this document has been executed on the live VPS.** Every step below that
touches the server is an owner-approved manual step. This repository never deploys by itself.

Files: `docker-compose.prod.yml`, `nginx/prod.conf`, `nginx/cloudflare-realip.conf`, `.env.production.example`,
`backend/Dockerfile` (collectstatic at build), `backend/config/settings/prod.py` (WhiteNoise). Development files
(`docker-compose.yml`, `docker-compose.vps.yml`, `nginx/default.conf`) are not modified in behavior.

## 1. Topology

    Browser --HTTPS--> Cloudflare (Full (strict)) --HTTPS--> nginx (origin certificate)
                                                              |-- /api/, /admin/, /static/ --> backend (gunicorn + WhiteNoise)
                                                              |-- everything else          --> frontend (Next.js standalone)
    backend --> postgres, redis   (internal network only, no published ports)

Only nginx publishes ports (80, 443). PostgreSQL and Redis have no `ports:` and sit on the `internal` network.
Every long-running service has `restart: unless-stopped` and a health check; startup order follows health
(`depends_on: condition: service_healthy`).

## 2. Cloudflare and TLS decisions

- Browser-to-Cloudflare TLS is terminated by Cloudflare's edge certificate (Universal SSL, included in Free).
- Cloudflare-to-origin TLS is a separate hop. Required mode: **Full (strict)**, with a **Cloudflare Origin CA
  certificate** (free, valid up to 15 years, trusted only by Cloudflare) installed on nginx.
- **Do not use Flexible.** The origin would receive plain HTTP, `X-Forwarded-Proto` would be `http`, and Django's
  `SECURE_SSL_REDIRECT` would redirect every request to itself (redirect loop), and the origin hop is unencrypted.
- Because TLS ends at nginx, `$scheme` is truthful, `SECURE_PROXY_SSL_HEADER` is safe, and no redirect loop occurs.
- If the DNS records are DNS-only (grey cloud), an Origin CA certificate is NOT trusted by browsers. Either turn
  proxying on (owner decision, made in Cloudflare, not by this repository) or use a publicly trusted certificate
  (for example Let's Encrypt) in the same `origin.pem` / `origin.key` slots. The compose and nginx files work with either.
- Checked 2026-10-19: `vedzmani.ir` and `www.vedzmani.ir` resolve (public resolver 1.1.1.1) to Cloudflare addresses
  and the zone's name servers are Cloudflare's, which matches proxied records. The Cloudflare SSL/TLS mode itself
  cannot be read from outside; it was owner-reported as `Full`. Decision: Cloudflare Origin CA for both hostnames.
- Do not switch the mode to `Full (strict)` until the origin certificate is installed and HTTPS through the
  origin has been tested (section 5, step 9).

## 3. Environment variables

Template: `.env.production.example`. Copy it to `.env.production` on the server (git-ignored), never commit it.
Required (compose fails fast if unset): `RELEASE_TAG`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_URL`,
`ORIGIN_CERT_DIR`. Optional: `PRIMARY_HOST`, `DJANGO_HSTS_SECONDS` (keep 0 until HTTPS is verified end to end).
`prod.py` refuses to boot with an empty host list, a development or placeholder secret key, or a dev OTP backend.

## 4. Cloudflare real client IP

`nginx/cloudflare-realip.conf` is committed empty on purpose: Cloudflare's ranges change, so they are generated at
deploy time from https://www.cloudflare.com/ips-v4 and https://www.cloudflare.com/ips-v6. Format:

    set_real_ip_from <each CIDR from the two lists>;
    real_ip_header CF-Connecting-IP;

Until it is filled, nginx trusts no forwarded header: safe, but every visitor appears as a Cloudflare address and
per-IP OTP rate limits are shared. Fill it before launch. nginx then overwrites `X-Forwarded-For` with the verified
client address, so the backend keeps `AUTH_TRUSTED_PROXY_COUNT=1`.

## 5. First deployment (owner-approved, manual)

Preconditions: owner approval; DNS and Cloudflare configured by the owner; a CI-green commit SHA; certificate files
`origin.pem` and `origin.key` in `ORIGIN_CERT_DIR` (mode 600 for the key, never in the repository).

1. `git fetch` and check out the approved SHA (no `reset --hard`, no `clean`).
2. Create `.env.production` from the template and fill it in.
3. Validate: `docker compose --env-file .env.production -f docker-compose.prod.yml config -q`
4. Build: `docker compose --env-file .env.production -f docker-compose.prod.yml build`
5. Start data services: `... up -d postgres redis`
6. Back up (empty on first deploy), then review the plan: `... --profile ops run --rm migrate-plan`
7. Apply migrations: `... --profile ops run --rm migrate`
8. Start the rest: `... up -d`
9. Verify: `... ps` shows all services healthy; `curl -I https://vedzmani.ir/` and `/api/health/`; open `/admin/`
   and confirm its CSS loads; confirm the HTTP-to-HTTPS redirect has no loop.

Never run `docker compose down -v`; it deletes the `postgres_data` volume.

## 6. Release and rollback

Images are tagged with the commit SHA (`RELEASE_TAG`), never `latest`, so the previous release stays on the host.
Release: back up, build the new SHA, run `migrate-plan`, run `migrate`, set `RELEASE_TAG`, `up -d backend frontend`.
Rollback of code: set `RELEASE_TAG` back to the previous SHA and run `up -d backend frontend`.
Migrations are not reverted automatically. If a release applied a migration the old code cannot run against,
roll back by restoring the pre-release database backup, with owner approval. Prefer backward-compatible migrations.

## 7. TLS renewal

Cloudflare edge certificates renew automatically. An Origin CA certificate has a fixed expiry (record it); replace
`origin.pem` and `origin.key` in `ORIGIN_CERT_DIR` before then and run `docker compose ... exec nginx nginx -s reload`.
A Let's Encrypt certificate needs a renewal job of its own; none is configured here.

## 8. Backups

Not automated by this repository. Minimum expectation: a `pg_dump` taken before every migration and on a schedule,
stored off the server, with a restore rehearsed on a throwaway database (never the production database), e.g.
`docker compose ... exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.sql`. Redis holds only
cache and rate-limit counters and is not backed up.

## 9. Known gaps before launch

- `nginx/cloudflare-realip.conf` still empty (section 4).
- No backup automation and no restore rehearsal (section 8).
- Certificate type: Origin CA chosen (proxying confirmed by DNS, section 2); the certificate itself does not exist yet.
- Sign-in: `prod.py` refuses console/in-memory OTP delivery and the default backend refuses to send, so customer
  sign-in (and therefore checkout) does not work until an SMS provider or a reviewed staging-only delivery exists.
- Payment: no provider; orders are created unpaid and must never be presented as paid.
- The prod stack uses its own Compose project (`vedzmani-prod`) and its own `postgres_data` volume: it starts with
  an EMPTY database. The development stack (`vedzmani-dev`, loopback 8080/5433) is a different project and is
  not touched; copying its data is a separate, owner-approved step.
- Docker-published ports bypass UFW; restricting 80/443 to Cloudflare ranges needs a `DOCKER-USER` rule (host-side).
- The stack has not been started on any server by this work.

## 8. First deployment on the VPS (2026-10-19)

Server-local layout (outside Git, owner `vzinfra`, directory mode 700): `~/prod/vedzmani` (checkout of the release
commit), `~/prod/.env.production` (mode 600, generated on the server), `~/prod/certs/{origin.pem,origin.key}`,
`~/prod/cloudflare-realip.conf` (generated from cloudflare.com/ips-v4 and ips-v6) and `~/prod/server.override.yml`
(mounts that file over `nginx/cloudflare-realip.conf`). Compose project `vedzmani-prod`; the development project
`vedzmani-dev` was not touched. Command prefix:

    docker compose --env-file ~/prod/.env.production -f ~/prod/vedzmani/docker-compose.prod.yml -f ~/prod/server.override.yml

- The certificate in use is TEMPORARY and self-signed (90 days). Cloudflare `Full` accepts it; `Full (strict)` does
  not. Replace `origin.pem`/`origin.key` with a Cloudflare Origin CA certificate, run `nginx -t`, recreate nginx, test
  with SNI, and only then switch to `Full (strict)`.
- When replacing a single bind-mounted file (certificate or real-IP list), recreate the container
  (`up -d --force-recreate --no-deps nginx`); a reload does not see a file replaced by `mv`.
- `DJANGO_ALLOWED_HOSTS` must include `backend` (see `.env.production.example`).
- The database starts empty. Create the first staff user interactively on the server
  (`... --profile ops run --rm migrate python manage.py createsuperuser`), never from a script that holds the password.
