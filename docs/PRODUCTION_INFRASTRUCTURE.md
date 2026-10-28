# Production infrastructure (Agent 1)

Status: prepared for review (PR #27). This document describes the files in this repository and the procedure they
are meant to be used with. **It is not evidence that anything is running, secure or ready for customers.** Merging
the PR deploys nothing (this repository never deploys by itself) and does not by itself make production
launch-ready; section 11 lists what is still open.

Files: `docker-compose.prod.yml`, `nginx/prod.conf`, `nginx/cloudflare-realip.conf`, `.env.production.example`,
`scripts/cloudflare_realip.py`, `scripts/validate_prod_stack.py`, `backend/Dockerfile` (collectstatic at build),
`backend/config/settings/prod.py` (WhiteNoise). Development files (`docker-compose.yml`, `docker-compose.vps.yml`,
`nginx/default.conf`) are not modified in behavior.

## 0. Evidence levels used in this document

Every statement about the real world carries one of these labels, so that a plan is never read as a result.

| Label | Meaning |
|---|---|
| **Code review** | Read from the files in this branch. Shows intent and configuration, says nothing about a running server. |
| **Automated test** | Executed by a script or CI job against repository files in a throwaway environment (section 10). Never touches production. |
| **Reported** | A manual action or observation stated by the owner or by an earlier revision of this document. No logs, command output or screenshots are in the repository, and the author of this revision could not confirm it. |
| **Production-verified** | Observed directly against the live system, with date and method. |

Current state of the main claims:

| Claim | Evidence | Status |
|---|---|---|
| Compose, Nginx and Django production settings are defined and consistent with each other | Code review, automated test (sections 9 and 10) | Defined. Not proof that they work on a server. |
| The stack was started on the VPS on 2026-10-19 | Reported (section 6) | **Reported but unverified.** |
| Cloudflare SSL/TLS mode is `Full` | Reported (owner) | Cannot be read from outside Cloudflare. Unverified. |
| The origin certificate in use is a temporary self-signed one | Reported (section 6) | Unverified. `Full (strict)` is therefore not in effect. |
| Real client IP restoration works on the VPS | Reported at most | **Not established.** The repository ships a placeholder (section 4); a populated server-local file is only reported. |
| `vedzmani.ir` and `www.vedzmani.ir` resolve to Cloudflare addresses | Production-verified, 2026-10-28 | Public lookup via resolver 1.1.1.1: both names return 172.67.207.101 and 104.21.61.80 (inside Cloudflare's published ranges); name servers for `vedzmani.ir` are `destiny.ns.cloudflare.com` and `seth.ns.cloudflare.com`. This shows the names are proxied by Cloudflare, not that the VPS answers correctly. |
| Off-server backups exist and a restore works | None | Not in the repository, never rehearsed (section 8). |

## 1. Topology (Code review)

    Browser --HTTPS--> Cloudflare --HTTPS--> nginx (origin certificate)
                                              |-- /api/, /admin/, /static/ --> backend (gunicorn + WhiteNoise)
                                              |-- everything else          --> frontend (Next.js standalone)
    backend --> postgres, redis   (internal network only, no published ports)

Only nginx publishes ports (80, 443). PostgreSQL and Redis have no `ports:` and sit on the `internal` network.
Every long-running service has `restart: unless-stopped` and a health check; startup order follows health
(`depends_on: condition: service_healthy`). The required Cloudflare SSL/TLS mode is `Full (strict)`; the mode
actually in effect is not known (section 0).

## 2. Cloudflare and TLS decisions

- Browser-to-Cloudflare TLS is terminated by Cloudflare's edge certificate (Universal SSL, included in Free).
- Cloudflare-to-origin TLS is a separate hop. Required mode: **Full (strict)**, with a **Cloudflare Origin CA
  certificate** (free, valid up to 15 years, trusted only by Cloudflare) installed on nginx. Decision: Origin CA for
  both hostnames.
- **Do not use Flexible.** The origin would receive plain HTTP, `X-Forwarded-Proto` would be `http`, and Django's
  `SECURE_SSL_REDIRECT` would redirect every request to itself (redirect loop), and the origin hop is unencrypted.
- Because TLS ends at nginx, `$scheme` is truthful, `SECURE_PROXY_SSL_HEADER` is safe, and no redirect loop occurs.
- If the DNS records are DNS-only (grey cloud), an Origin CA certificate is NOT trusted by browsers. Either turn
  proxying on (owner decision, made in Cloudflare, not by this repository) or use a publicly trusted certificate
  (for example Let's Encrypt) in the same `origin.pem` / `origin.key` slots. The compose and nginx files work with either.
- Proxying: the 2026-10-28 DNS lookup in section 0 matches proxied records. The SSL/TLS mode itself cannot be read
  from outside; it was owner-reported as `Full`.
- Do not switch the mode to `Full (strict)` until a valid origin certificate is installed and HTTPS through the
  origin has been tested (section 5, step 9).

## 3. Environment variables

Template: `.env.production.example`. Copy it to `.env.production` on the server (git-ignored), never commit it.
Required (compose fails fast if unset): `RELEASE_TAG`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_URL`,
`ORIGIN_CERT_DIR`. Optional: `PRIMARY_HOST`, `DJANGO_HSTS_SECONDS` (keep 0 until HTTPS is verified end to end).
`prod.py` refuses to boot with an empty host list, a development or placeholder secret key, or a dev OTP backend.
An automated test keeps the template and the compose file in step (section 10).

## 4. Cloudflare real client IP

### 4.1 What the repository ships

`nginx/cloudflare-realip.conf` is a **placeholder with no directives**. Used as it is, Nginx trusts no forwarded
header, so **real client IP restoration is not active**: every visitor appears with a Cloudflare edge address and
per-address limits (admin-login throttle, OTP rate limits) are shared between visitors. This is safe but coarse.
Do not describe real-IP handling as operational on any server until a populated file has been mounted and checked.

### 4.2 How it works when populated (Code review, Automated test)

The generated include lists Cloudflare's ranges with `set_real_ip_from`, sets `real_ip_header CF-Connecting-IP` and
`real_ip_recursive off`. Nginx then replaces the client address with `CF-Connecting-IP` **only when the TCP peer is
inside one of those ranges**. From any other peer the header is ignored, so a client that reaches the origin directly
cannot choose its own address. `nginx/prod.conf` then sets `X-Forwarded-For` to `$remote_addr` (overwrite, never
append), so a client-supplied `X-Forwarded-For` never reaches the backend, which keeps `AUTH_TRUSTED_PROXY_COUNT=1`.
The directive `real_ip_header` must stay `CF-Connecting-IP`: Nginx's default is `X-Real-IP`, which clients can send.

### 4.3 Getting and updating the ranges

The ranges are never committed. `scripts/cloudflare_realip.py` (standard library only, no credentials, no
Cloudflare dashboard or API) downloads the two public lists and writes the include:

    python3 scripts/cloudflare_realip.py generate --output <server-path>/cloudflare-realip.conf
    python3 scripts/cloudflare_realip.py check <server-path>/cloudflare-realip.conf --require-populated --max-age-days 45

Lists: https://www.cloudflare.com/ips-v4 and https://www.cloudflare.com/ips-v6. The script fails closed and writes
nothing when: a source is not HTTPS or answers with an error or an oversized body; a line is not a strict CIDR of
the right IP version; a range is not publicly routable (private, loopback, link-local, documentation, ...) or is
broader than /12 (IPv4) or /24 (IPv6); or fewer than 5 IPv4 or 3 IPv6 ranges came back. The file is replaced
atomically and carries a `# Generated:` date so `check --max-age-days` can flag a stale file. The ranges in
`scripts/testdata/` are test fixtures only; they are never installed anywhere.

To use the generated file on a server, mount it over `/etc/nginx/cloudflare-realip.conf` with a server-local
Compose override (outside Git). Compose merges volumes by container path, so this replaces the repository placeholder
(checked with `docker compose config`):

    # server.override.yml
    services:
      nginx:
        volumes:
          - <server-path>/cloudflare-realip.conf:/etc/nginx/cloudflare-realip.conf:ro

    docker compose --env-file .env.production -f docker-compose.prod.yml -f server.override.yml ...

Before replacing the file under a running nginx, test the new one with a throwaway container so that a bad file
cannot take the site down (owner-approved server step, not run by this repository):

    docker run --rm --add-host backend:127.0.0.1 --add-host frontend:127.0.0.1 \
      -v "$PWD/nginx/prod.conf:/etc/nginx/conf.d/default.conf:ro" \
      -v "<new-file>:/etc/nginx/cloudflare-realip.conf:ro" \
      -v "$ORIGIN_CERT_DIR:/etc/nginx/certs:ro" nginx:1.27-alpine nginx -t

Then recreate nginx (`up -d --force-recreate --no-deps nginx`): a reload does not see a bind-mounted file that was
replaced by rename (reported in section 6, consistent with how bind mounts behave).

Cadence: regenerate at least monthly and whenever Cloudflare announces a change. No timer or cron job is installed
by this repository. If one is added, it should only regenerate and pre-check the file; recreating nginx stays a
deliberate step until the whole path has been exercised on a real server.

### 4.4 Limits: what this does not establish

- Server-side files. Whether a populated include exists on the VPS and is the one mounted cannot be seen from the
  repository (section 6 only reports it). To confirm, run the `check ... --require-populated` command above on the
  server against the mounted file.
- The automated tests (section 10) prove the files and the Nginx logic against a throwaway Nginx. They do not prove
  how Cloudflare behaves in production (for example that every request carries `CF-Connecting-IP`).
- Direct origin access. Docker publishes 80 and 443 on all interfaces and bypasses UFW. Anyone who finds the origin
  address can connect to it without passing through Cloudflare (no edge WAF or rate limiting). Real-IP handling keeps
  such a client from spoofing its address, but does not stop the access. Restricting 80/443 to Cloudflare ranges needs
  a host-side `DOCKER-USER` rule or Authenticated Origin Pulls; neither is in this repository.

## 5. First deployment procedure (plan; owner-approved, manual)

This is the procedure the files are designed for. It is not a record of what was done (see section 6).

Preconditions: owner approval; DNS and Cloudflare configured by the owner; a CI-green commit SHA; certificate files
`origin.pem` and `origin.key` in `ORIGIN_CERT_DIR` (mode 600 for the key, never in the repository); a populated
real-IP include (section 4.3) if per-visitor rate limits are wanted.

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

## 6. First VPS deployment of 2026-10-19: reported but unverified

Source: the earlier revision of this document (commit `b0a5547`), which contained a section titled "First deployment
on the VPS (2026-10-19)". The repository holds no command output, logs, screenshots or health-check results for it,
and the author of this revision had no access to the server. **Treat every statement below as a claim for the owner
to confirm, not as a fact.**

The earlier revision contradicted itself: its introduction and its list of gaps said nothing had been executed on
the VPS and that the stack had not been started on any server, while this section said it had. Neither side can be
confirmed from the repository, so those "nothing executed" statements were removed and the deployment is recorded
here as reported but unverified. The PR's own description ("Nothing is deployed by this change") stays correct: the
PR changes files and does not deploy.

What was reported:

- Server-local layout outside Git, on a dedicated server account (name omitted), directory mode 700:
  `~/prod/vedzmani` (checkout of the release commit), `~/prod/.env.production` (mode 600, generated on the server),
  `~/prod/certs/{origin.pem,origin.key}`, `~/prod/cloudflare-realip.conf` (generated from the two Cloudflare lists)
  and `~/prod/server.override.yml` (mounts that file over `nginx/cloudflare-realip.conf`). Compose project
  `vedzmani-prod`; the development project `vedzmani-dev` was not touched.
- The certificate in use is TEMPORARY and self-signed (90 days). Cloudflare `Full` accepts it; `Full (strict)` does
  not. Replace `origin.pem`/`origin.key` with a Cloudflare Origin CA certificate, run `nginx -t`, recreate nginx, test
  with SNI, and only then switch to `Full (strict)`.
- The database starts empty. The first staff user is to be created interactively on the server
  (`... --profile ops run --rm migrate python manage.py createsuperuser`), never from a script that holds the password.

Operational notes from that report:

- When replacing a single bind-mounted file (certificate or real-IP list), recreate the container
  (`up -d --force-recreate --no-deps nginx`); a reload does not see a file replaced by `mv`.
- `DJANGO_ALLOWED_HOSTS` must include `backend`. Code review agrees: the frontend calls the API at
  `http://backend:8000` (`API_INTERNAL_URL` in `docker-compose.prod.yml`), so Django receives that Host. The reported
  HTTP 400 failure without it is itself unverified.

Things that would turn this section into verified facts: deployment logs or `docker compose ps` output with dates,
the server's `git rev-parse HEAD`, the result of the `check` command in section 4.3 on the mounted file, and the
Cloudflare SSL/TLS mode read from the dashboard by the owner.

## 7. Release and rollback (documented, never exercised)

Images are tagged with the commit SHA (`RELEASE_TAG`), never `latest`, so the previous release stays on the host.
Release: back up, build the new SHA, run `migrate-plan`, run `migrate`, set `RELEASE_TAG`, `up -d backend frontend`.
Rollback of code: set `RELEASE_TAG` back to the previous SHA and run `up -d backend frontend`.
Migrations are not reverted automatically. If a release applied a migration the old code cannot run against,
roll back by restoring the pre-release database backup, with owner approval. Prefer backward-compatible migrations.
No release or rollback has been rehearsed and recorded in this repository.

## 8. TLS renewal and backups

TLS renewal: Cloudflare edge certificates renew automatically. An Origin CA certificate has a fixed expiry (record
it); replace `origin.pem` and `origin.key` in `ORIGIN_CERT_DIR` before then and recreate nginx. A Let's Encrypt
certificate needs a renewal job of its own; none is configured here. If the temporary self-signed certificate
(section 6) was created on 2026-10-19 with a 90-day lifetime, it expires around 2027-01-17 (derived from the
reported facts, not observed).

Backups: **not automated by this repository, and no restore has been tested.** Minimum expectation: a `pg_dump`
taken before every migration and on a schedule, stored off the server, with a restore rehearsed on a throwaway
database (never the production database), e.g.
`docker compose ... exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.sql`. Redis holds
only cache and rate-limit counters and is not backed up.

## 9. What CI and the tests cover (Automated test)

- `backend` job (existing): `manage.py check --deploy --fail-level WARNING` on `config.settings.prod` with throwaway
  values, plus pytest, which includes static guards for these files in `backend/tests/test_prod_infra_config.py`:
  only nginx publishes ports (80 and 443); images are pinned; `.env.production.example` defines every variable the
  compose file requires and keeps secrets as placeholders; Nginx never forwards client-supplied addresses and rejects
  unknown TLS names; the committed real-IP file is valid; and the generator and checker in
  `scripts/cloudflare_realip.py` reject unsafe or malformed input and never replace a good file with a bad one.
- `prod-config` job (new): runs `python3 scripts/validate_prod_stack.py`, described in section 10.

## 10. Production configuration validation

Run from the repository root; needs Python 3, Docker and `openssl`; no secrets, no network access to production:

    python3 scripts/validate_prod_stack.py              # both groups
    python3 scripts/validate_prod_stack.py --only compose
    python3 scripts/validate_prod_stack.py --only nginx
    python3 scripts/cloudflare_realip.py check nginx/cloudflare-realip.conf    # reports PLACEHOLDER or POPULATED

What it proves:

- `docker compose config -q` accepts `docker-compose.prod.yml` with values derived from `.env.production.example`
  (placeholders replaced by dummies), and still fails fast when required variables are missing. Nothing is started.
- `nginx -t` accepts `nginx/prod.conf` with the committed placeholder and with an include generated from the offline
  fixtures, in the pinned `nginx` image from the compose file, with a throwaway self-signed certificate created for
  the test and fake upstream names. A deliberately broken include is rejected, which shows the include is read.
- Through a real proxy hop in a throwaway Docker network: from an untrusted peer, forged `CF-Connecting-IP`,
  `X-Real-IP` and `X-Forwarded-For` are ignored; from a trusted peer, `CF-Connecting-IP` becomes the client address
  and a forged `X-Forwarded-For` is overwritten; a malformed `CF-Connecting-IP` is ignored; an unknown SNI is refused
  at the TLS handshake and an unknown `Host` is not proxied (observed answer: 404).

What it does not prove (no reliable check is possible from a repository): the real origin certificate, its chain or
expiry; Cloudflare's SSL/TLS mode or headers; the contents of any file on the VPS; firewall or Docker port exposure
on the server; that the production images build or start (this validation builds and starts none of them, only a
throwaway Nginx); or anything about the live site.

## 11. Known gaps and risks before launch

- **Real client IP**: placeholder in the repository; a populated file on the VPS is only reported (section 4).
- **Direct origin access**: the compose file publishes 80/443 on all interfaces, so unless a host firewall rule
  exists (none is in the repository, and none was checked) the origin can be reached without Cloudflare; no
  Authenticated Origin Pulls either (section 4.4).
- **TLS Full (strict)**: not in effect according to the report; the origin certificate in use is reported as
  temporary and self-signed (sections 2 and 6).
- **Backups**: no automation, no off-server copy, no tested restore (section 8).
- **SMS provider**: none. `prod.py` refuses console/in-memory OTP delivery and the default backend
  (`UnconfiguredDelivery`) refuses to send, so customer sign-in, and therefore checkout, cannot work until a provider
  or a reviewed staging-only delivery exists.
- **Payment provider and order/stock policy**: no payment provider (`backend/PAYMENT.md`); orders are created unpaid
  and must never be presented as paid. Order and stock rules are not decided or reviewed in this document.
- The prod stack uses its own Compose project (`vedzmani-prod`) and its own `postgres_data` volume, so it starts with
  an EMPTY database. The development stack (`vedzmani-dev`, loopback 8080/5433) is a different project; copying its
  data is a separate, owner-approved step.
- `DJANGO_HSTS_SECONDS` stays 0 until HTTPS is verified end to end.
