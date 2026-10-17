# VPS development environment

Shared development environment for Vedzmani on a single Ubuntu VPS. **Development only — not production.**
Last verified: 2026-10-17 (see "Verification record" for what was actually executed).

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

The `catalog`, `checkout` and `signin` specs seed or create data and use a dev-only OTP/session helper. Run them **only** on an isolated stack (own project name, ports and database volume) as described in `e2e/README-signin.md`.

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
- `127.0.0.1:8080` -> Nginx, `127.0.0.1:5433` -> PostgreSQL. Redis, backend (8000) and frontend (3000) are not published to the host.
- Docker-published ports bypass UFW, which is why the override binds to loopback. Public HTTP/HTTPS, DNS changes and TLS require explicit owner approval.

## 8. Proposed multi-agent access model (not yet applied)

Separate SSH key per human or agent; individual Linux accounts where practical; one worktree per branch; integration only through GitHub PRs; secret files readable only by their owner; no shared root credentials; no automatic production deployment. Docker group membership is root-equivalent: grant it only with owner approval. Any new account or privilege needs a written proposal and owner authorization first.

## 9. Known issues and production limitations

- Runs Django development settings (`config.settings.dev`); production settings (`prod`) are not exercised here.
- No SMS provider: OTP uses the dev-only console delivery, so tests say nothing about real SMS.
- No off-server backups, no monitoring/alerting stack, no TLS, no public ingress.
- SSH root/password login hardening and recovery-console access have not been confirmed; the owner should verify them.
- Core Web Vitals (LCP/INP/CLS) have not been measured.

## 10. Verification record (2026-10-17)

| Check | Result |
| --- | --- |
| `manage.py check` / `makemigrations --check` | no issues / no changes |
| `pytest` (isolated PostgreSQL 16) | 519 passed |
| Frontend `pnpm install --frozen-lockfile`, `lint`, `typecheck`, `build` | all exit 0 (26 static pages; `.next/static` 764 KB) |
| Playwright (`smoke`, `storefront`, `auth-redirect`) | 32 passed |
| Playwright (`catalog`, `checkout`, `signin`) | not run (need an isolated seeded stack) |
| Backup + restore into temp DB | 24 public tables and 24 `django_migrations` rows in both |
| Latency, 20 sequential requests via Nginx on loopback | `/en` median 3 ms (max 5 ms); `/api/health/ready/` median 3 ms (max 75 ms) |
| Resources, idle | about 510 MiB RAM used of 7.8 GiB; disk 11% of 97 GB; 0 restarts, all services healthy |

Latency numbers are loopback, idle, `curl`, single client; `/en` is pre-rendered, so they are not a load or browser-performance result.
