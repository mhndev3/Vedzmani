# VPS development environment

Shared development environment for Vedzmani on a single Ubuntu VPS. **Development only — not production.**
Last updated: 2026-10-17 (see "Verification record" for what was actually executed).

Status labels used below: **verified** = executed and checked by the author of this revision;
**previously reported** = result reported by an earlier session and not re-executed here;
**documented, not executed** = derived from the repository files but not run;
**owner approval required** = must not be done without the owner's explicit authorization.

## 1. Layout

| Item | Value |
| --- | --- |
| OS | Ubuntu 22.04 LTS |
| Admin user | `vzadmin` (SSH key authentication) |
| Project root | `/srv/vedzmani` |
| Main checkout | `/srv/vedzmani/main` |
| Worktrees | `/srv/vedzmani/worktrees/<branch-name>` |
| Infra worktree | `/srv/vedzmani/worktrees/infra-vps-development-environment` (branch `infra/vps-development-environment`) |
| Backups | `/srv/vedzmani/backups` (directory mode `700`, files mode `600`) |
| Compose project | `vedzmani-dev` (services: `postgres`, `redis`, `backend`, `frontend`, `nginx`) |

Use one worktree per branch (`git worktree add`); never switch branches inside another agent's worktree.

## 2. Access

```bash
ssh -i "$HOME/.ssh/<your_private_key>" -o IdentitiesOnly=yes vzadmin@<VPS_IP>
```

- Private keys stay on the owner's or agent's own machine. Never copy them to the VPS, the repository, chat or another agent.
- Never share or paste passwords, tokens or `.env` contents. Any credential disclosed in chat must be rotated.
- The app is reachable only through an SSH tunnel (Nginx and PostgreSQL are bound to loopback):

```bash
ssh -L 8080:127.0.0.1:8080 -i "$HOME/.ssh/<your_private_key>" vzadmin@<VPS_IP>
# then open http://localhost:8080
```

## 3. Docker Compose

Always use both files (`docker-compose.vps.yml` binds PostgreSQL and Nginx to `127.0.0.1` and sets `restart: unless-stopped`):

```bash
cd /srv/vedzmani/worktrees/infra-vps-development-environment
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs --tail=100 backend
```

**Never use the `-v` flag with `docker compose down`**: it deletes the PostgreSQL volume. Prefer `restart <service>`.

Health checks: `curl -fsS http://127.0.0.1:8080/api/health/ready/` and `curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/en`.

### Environment variable names (values live only in the untracked `.env`)

`COMPOSE_PROJECT_NAME`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `HTTP_PORT`, `NEXT_PUBLIC_API_URL`. Optional: `POSTGRES_HOST_PORT`. Use `.env.example` as the template. `.env` must stay mode `600` and out of Git.

## 4. Tests

Run tests in throwaway containers with a throwaway database. **Never point tests at the dev database.** These mirror `.github/workflows/ci.yml`.

### Backend (Python 3.13, PostgreSQL 16, `config.settings.test`)

```bash
docker network create vz-test-net
docker run -d --name vz-test-pg --network vz-test-net --tmpfs /var/lib/postgresql/data \
  -e POSTGRES_DB=vedzmani -e POSTGRES_USER=vedzmani -e POSTGRES_PASSWORD=vedzmani postgres:16-alpine
# wait until: docker exec vz-test-pg pg_isready -U vedzmani
docker run --rm --network vz-test-net -v "$PWD/backend:/src:ro" \
  -e DJANGO_SETTINGS_MODULE=config.settings.test -e DJANGO_SECRET_KEY=ci-only-not-a-secret \
  -e DATABASE_URL=postgres://vedzmani:vedzmani@vz-test-pg:5432/vedzmani \
  -e REDIS_URL=redis://localhost:6379/0 -e PYTHONDONTWRITEBYTECODE=1 python:3.13-slim sh -c \
  'cp -r /src /tmp/app && cd /tmp/app && pip install -q -r requirements/dev.txt \
   && python manage.py check && python manage.py makemigrations --check --dry-run && pytest -p no:cacheprovider'
docker rm -f vz-test-pg && docker network rm vz-test-net
```

### Frontend (Node 24, pnpm via corepack, lockfile enforced)

```bash
docker run --rm -v "$PWD/frontend:/src:ro" -e NEXT_TELEMETRY_DISABLED=1 -e API_INTERNAL_URL=http://localhost:8000 \
  node:24-alpine sh -c 'corepack enable && mkdir /app && cd /src \
  && tar cf - --exclude=node_modules --exclude=.next . | tar xf - -C /app && cd /app \
  && pnpm install --frozen-lockfile && pnpm lint && pnpm typecheck && pnpm build'
```

### Playwright (`e2e/`)

Read-only specs (`smoke`, `storefront`, `auth-redirect`) may run against the dev stack on loopback:

```bash
docker run --rm --network host -v "$PWD:/src:ro" -e E2E_BASE_URL=http://127.0.0.1:8080 \
  mcr.microsoft.com/playwright:v1.64.1-noble sh -c 'mkdir -p /w/frontend && cp -r /src/e2e /w/e2e \
  && cp -r /src/frontend/src /w/frontend/src && cd /w/e2e \
  && npm i --no-audit --no-fund @playwright/test@1.64.1 @types/node@20 \
  && npx playwright test tests/smoke.spec.ts tests/storefront.spec.ts tests/auth-redirect.spec.ts'
```

#### Isolated E2E stack (`catalog`, `checkout`, `signin`)

These specs seed fixture data, create users and sessions through `e2e/e2e_helper.py`, and (`signin`) read one-time codes from backend logs. Run them **only** against a throwaway stack with its own Compose project name, host ports and PostgreSQL volume. Never point them at `vedzmani-dev`.

**Status: previously reported (Session 5), documented, not executed in this revision.** The Session 5 override and environment files were temporary and no longer exist, so the steps below are reconstructed from `docker-compose.yml`, `docker-compose.vps.yml`, `e2e/README-signin.md`, `e2e/playwright.config.ts` and the specs. This is a multi-step workflow with prerequisites, not a one-command operation. Only the Compose invocation syntax was verified (with a dummy environment and `config` only; nothing was created).

| Item | Dev stack | Isolated E2E stack |
| --- | --- | --- |
| Compose project | `vedzmani-dev` | unique name per run (Session 5: `vzs5e2e`) |
| Nginx host binding | `127.0.0.1:8080` | its own loopback port (Session 5: `127.0.0.1:18091`) |
| PostgreSQL host binding | `127.0.0.1:5433` | its own loopback port (Session 5: `127.0.0.1:15432`) |
| PostgreSQL volume | `vedzmani-dev_postgres_data` | project-prefixed volume created by that project (Session 5: `vzs5e2e_postgres_data`) |
| Env and override files | worktree `.env` (mode `600`) | new files outside the repository (Session 5: under `/tmp/vzs5e2e`) with freshly generated throwaway secrets |

**1. Create the temporary files** (never print them, never commit them): a directory outside the repository with mode `700`, containing an env file copied from `.env.example` and a test-only override. In the env file set `COMPOSE_PROJECT_NAME`, a free `HTTP_PORT` and `POSTGRES_HOST_PORT` (the VPS overlay binds both to loopback), new random URL-safe `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY`, and `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` and `NEXT_PUBLIC_API_URL` set to the isolated Nginx origin. The override raises the OTP rate limits **for this test stack only** (many sign-ins come from one IP):

```yaml
services:
  backend:
    environment:
      OTP_REQUEST_IP_LIMIT: "1000"
      OTP_VERIFY_IP_LIMIT: "1000"
```

Never raise these limits in a shared or production-like environment.

**2. Start the stack.** Always pass `-p` and `--env-file` explicitly, otherwise Compose reads the worktree `.env` (dev values):

```bash
cd /srv/vedzmani/worktrees/infra-vps-development-environment
E="docker compose --env-file /tmp/<project>/env -p <project> -f docker-compose.yml -f docker-compose.vps.yml -f /tmp/<project>/compose.e2e.yml"
$E up -d --build
$E ps
$E exec -T backend python manage.py migrate
```

**3. Seed the fixture catalog** (idempotent; `e2e/seed_catalog.py` is E2E-only data) by copying it into the backend container and executing it in `manage.py shell` with `E2E_THROWAWAY_DB=1` (the seeder refuses to run without it; the flag is your confirmation that this is the isolated project, not proof) (documented, not executed):

```bash
$E cp e2e/seed_catalog.py backend:/tmp/seed_catalog.py
$E exec -T -e E2E_THROWAWAY_DB=1 backend python manage.py shell -c "exec(open('/tmp/seed_catalog.py', encoding='utf-8').read())"
```

**4. Verify the runner targets the isolated database before seeding or running the helper.** `checkout.spec.ts` runs `e2e/e2e_helper.py` on the host through `manage.py shell` in `E2E_BACKEND_DIR`, using the same `DATABASE_URL` and `REDIS_URL` as the running test server. Before the first helper call, confirm the host and port in `DATABASE_URL` are the isolated PostgreSQL port and not `5433`, without printing the password:

```bash
python3 -c "import os,urllib.parse as u; p=u.urlparse(os.environ['DATABASE_URL']); print(p.hostname, p.port, p.path)"
```

(The snippet's syntax was verified with a dummy value.) The helper creates users and sessions and can change stock, so a wrong target would modify real data. The helper also refuses to run unless `E2E_THROWAWAY_DB=1` is set and the settings module is `config.settings.dev` or `config.settings.test`. The dev stack uses `config.settings.dev` too, so that check cannot tell the isolated database from `vedzmani-dev`: the host/port check above is the real control, and the flag only records that you made it. Set the flag on the command that needs it, never in a shell profile. How Session 5 supplied the helper's database and cache environment is not recorded in the repository; record it the next time this workflow is run. Session 5 reported that the helper ran under Python 3.12 while the backend container uses Python 3.13.

**5. Run the three suites** from `e2e/` (install `@playwright/test` as in the smoke command above, or use the existing `e2e/package.json`):

```bash
E2E_BASE_URL=http://127.0.0.1:<nginx-port> \
E2E_BACKEND_DIR=<absolute path to backend/> \
E2E_PYTHON=<python that has backend/requirements> \
E2E_THROWAWAY_DB=1 \
E2E_OTP_LOG_COMMAND="docker compose -p <project> logs --no-color backend" \
npx playwright test tests/catalog.spec.ts tests/checkout.spec.ts tests/signin.spec.ts
```

`E2E_BROWSER_CHANNEL` (for example `msedge` or `chrome`) is optional and only needed when the bundled Chromium cannot be used. Without `E2E_BACKEND_DIR`, the signed-in checkout tests are skipped; without `E2E_OTP_LOG_COMMAND`, the "real OTP flow" signin tests are skipped. A run with skips is not a full run: confirm the report shows 0 skipped.

**OTP delivery is test-only.** The test backend runs `config.settings.dev`, whose dev-only `ConsoleDelivery` writes the code to the backend log, and the signin spec reads it from there. **No SMS was sent and no SMS provider is configured.** Never point `E2E_OTP_LOG_COMMAND` at a stack with real customers.

**6. Clean up only your own project.** Do not use `docker compose down -v`. Stop the isolated project, list its volumes by label, and remove only what that listing returns for your own unique project name (never `vedzmani-dev` or another agent's project):

```bash
$E down
docker volume ls --filter label=com.docker.compose.project=<project> --format '{{.Name}}'
docker volume rm <volume-name-from-the-listing-above>
rm -r /tmp/<project>
```

(`$E down` and the removal commands were not executed in this revision. The label-filtered `docker volume ls` syntax was verified read-only against the dev project.)

**Reported results (Session 5, isolated stack, not re-executed in this revision):**

| Suite | Passed | Failed | Skipped | Reported duration |
| --- | ---: | ---: | ---: | ---: |
| `catalog` | 16 | 0 | 0 | 13.2 s |
| `checkout` | 10 | 0 | 0 | 14.6 s |
| `signin` | 21 | 0 | 0 | 12.3 s |
| **Total** | **47** | **0** | **0** | |

These are functional UI/API test results on development settings with a raised test-only OTP rate limit. They are **not** production-security verification and say nothing about real SMS delivery.

## 5. PostgreSQL backup and restore verification

Backup (custom format; password never printed; restricted destination; fails loudly):

```bash
set -euo pipefail
cd /srv/vedzmani/worktrees/infra-vps-development-environment
C="docker compose -f docker-compose.yml -f docker-compose.vps.yml"
umask 077
f=/srv/vedzmani/backups/vedzmani-dev-$(date -u +%Y%m%d-%H%M%S).dump
$C exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$f.tmp"
test -s "$f.tmp" && mv "$f.tmp" "$f" && chmod 600 "$f"
stat -c '%U %G %a %s %n' "$f"
```

Restore verification (separate temporary database; the dev database is never modified). When these lines run inside a script, give every `exec -T` that needs no input `</dev/null`, otherwise it consumes the rest of the script from stdin.

```bash
$C exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" restore_check' </dev/null
$C exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d restore_check --no-owner --exit-on-error' < "$f"
echo "select count(*) from information_schema.tables where table_schema='public'" | \
  $C exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d restore_check -At'
# compare with the same query against "$POSTGRES_DB", then drop the temporary database:
$C exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" --if-exists restore_check' </dev/null
```

Restoring over the real dev database is a separate, owner-approved operation. **Off-server backup is NOT configured**: all backups live on the same VPS and are lost with it. Never commit dumps to Git.

## 6. Restart and recovery

- After a reboot the stack returns by itself (`restart: unless-stopped`). Check: `docker compose ... ps` (all `healthy`), the two health URLs above, `sudo ufw status verbose`, `systemctl is-active docker fail2ban`.
- Restart one service: `docker compose ... restart backend`. Rebuild after code changes: `up -d --build <service>`.
- Never reset, clean or force-push shared worktrees to "fix" state; investigate first.

## 7. Network exposure (verified 2026-10-17)

- Public listener: SSH (22) only. UFW: default deny incoming, allow 22.
- `127.0.0.1:8080` -> Nginx, `127.0.0.1:5433` -> PostgreSQL. Redis, backend (8000) and frontend (3000) are not published to the host. Re-verified in the latest revision from `docker compose ... config` (ports only), `docker ps` and `ss -ltn`: the only non-loopback TCP listener is SSH (22).
- Docker-published ports bypass UFW, which is why the override binds to loopback. Public HTTP/HTTPS, DNS changes and TLS require explicit owner approval.

## 8. Proposed multi-agent access model (not yet applied)

Separate SSH key per human or agent; individual Linux accounts where practical; one worktree per branch; integration only through GitHub PRs; secret files readable only by their owner; no shared root credentials; no automatic production deployment. Docker group membership is root-equivalent: grant it only with owner approval. Any new account or privilege needs a written proposal and owner authorization first.

## 9. Known issues and production limitations

- Runs Django development settings (`config.settings.dev`); production settings (`prod`) are not exercised here.
- No SMS provider: OTP uses the dev-only console delivery, so tests say nothing about real SMS.
- No off-server backups, no monitoring/alerting stack, no TLS, no public ingress.
- SSH root/password login hardening and recovery-console access have not been confirmed; the owner should verify them.
- Core Web Vitals (LCP/INP/CLS) have not been measured.
- The isolated E2E workflow (section 4) was run once by a previous session and is reconstructed here; its temporary files are gone, the helper's database/cache environment is not recorded, and the workflow has not been re-executed since. The E2E stack used development Django settings and a test-only OTP rate-limit override, so the results are not production-security verification.
- Other Compose projects or volumes on this VPS may belong to other agents or sessions. Do not stop, modify or delete them.
- Off-server backup is not configured or verified (section 5).

## 10. Verification record (2026-10-17)

| Check | Result |
| --- | --- |
| `manage.py check` / `makemigrations --check` | no issues / no changes |
| `pytest` (isolated PostgreSQL 16) | 519 passed |
| Frontend `pnpm install --frozen-lockfile`, `lint`, `typecheck`, `build` | all exit 0 (26 static pages; `.next/static` 764 KB) |
| Playwright (`smoke`, `storefront`, `auth-redirect`) | 32 passed |
| Playwright (`catalog`, `checkout`, `signin`), isolated stack, Session 5 | 47 passed, 0 failed, 0 skipped (16 / 10 / 21); previously reported, not re-executed |
| Playwright, all six specs | 79 = 32 + 47: the sum of two previous-session reports, not a single run |
| Backup + restore into temp DB | 24 public tables and 24 `django_migrations` rows in both |
| Latency, 20 sequential requests via Nginx on loopback | `/en` median 3 ms (max 5 ms); `/api/health/ready/` median 3 ms (max 75 ms) |
| Resources, idle | about 510 MiB RAM used of 7.8 GiB; disk 11% of 97 GB; 0 restarts, all services healthy |

Latency numbers are loopback, idle, `curl`, single client; `/en` is pre-rendered, so they are not a load or browser-performance result.

Unless stated otherwise, the rows above are results reported by earlier sessions and were not re-executed when this document was last updated.

Re-checks executed when this document was last updated (all read-only; no tests were re-run):

| Check | Result |
| --- | --- |
| Branch `infra/vps-development-environment` at `49fef906b608e2ff8d3879c924bc8ec7e076f647`; working tree | clean before the documentation edit; `git diff --check` exit 0 |
| `docker compose -f docker-compose.yml -f docker-compose.vps.yml config --quiet` | exit 0 |
| Resolved host bindings | Nginx `127.0.0.1:8080`, PostgreSQL `127.0.0.1:5433`; Redis, backend, frontend not published; all five services `restart: unless-stopped` |
| Isolated-stack Compose invocation (dummy env file, `-p`, override; `config` only) | exit 0; Nginx and PostgreSQL on loopback; OTP limits resolved from the override; no containers or volumes created |
| Newest dump (`pg_restore --list`, no database connection, no restore) | readable, 218 table-of-contents lines, exit 0 |
| Backups directory and `.env` | directory mode `700`, both dumps mode `600`; `.env` mode `600` and not tracked by Git |
| Paths referenced by this document | all exist in the worktree |
| Services | `docker` and `fail2ban` active |
