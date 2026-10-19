# Vedzmani

Production-grade fashion e-commerce platform. **Modular monolith**: Next.js frontend + Django/DRF backend.
Authoritative contract: [`PROJECT_CONTROL.md`](PROJECT_CONTROL.md). This README covers architecture, environment, testing and CI. Implemented V1 features are described in `PROJECT_CONTROL.md` and the contracts in `backend/*.md`. Production SMS login, online payment, shipping fees and release of stock held by unpaid orders are **not** implemented.

## Architecture

```
Client -> CDN/WAF -> Nginx -> Next.js (/)
                           -> Django/DRF (/api/, /admin/) -> PostgreSQL, Redis
```

- **Django/DRF owns all business logic** (auth, products, inventory, cart, orders, pricing, payments boundaries). Next.js is presentation only.
- **PostgreSQL** (Django ORM) is the only source of truth. **Redis** is cache/short-lived state only — never authoritative for inventory, orders or payments.
- **Celery** is intentionally NOT added yet; introduce it (Redis broker) when the first justified async job appears.
- Forbidden by default: microservices, Kubernetes, Kafka, Elasticsearch/OpenSearch, GraphQL, second DB.

## Repository structure

```
backend/    Django project (config/, apps/ accounts, catalog, cart, orders, inventory, core; tests/, requirements/; API contracts in *.md)
frontend/   Next.js App Router, TypeScript strict, Tailwind v4, shadcn-compatible
e2e/        Playwright suite (separate package): smoke, storefront, catalog, sign-in, checkout, purchase journey
docs/       V1 readiness audit (historical snapshot), production readiness audit (2026-10-18), VPS development environment
nginx/      Reverse-proxy config
.github/    CI and E2E workflows
docker-compose.yml, docker-compose.vps.yml, .env.example
```

## Environment

Copy the example files; never commit real `.env` files.

| File | Used by |
|---|---|
| `.env.example` -> `.env` | Docker Compose |
| `backend/.env.example` | Backend run outside Docker |
| `frontend/.env.example` -> `frontend/.env.local` | Frontend run outside Docker |

Key variables: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `NEXT_PUBLIC_API_URL`, `API_INTERNAL_URL`.

Settings modules: `config.settings.dev` (local), `prod` (fails fast on missing/insecure config), `test`. `wsgi.py`/`asgi.py` default to `prod`.

**Compose is a development topology.** `docker-compose.yml` sets `DJANGO_SETTINGS_MODULE=config.settings.dev` for the
backend, so OTP codes use the dev-only `ConsoleDelivery` (written to the backend log). No SMS provider and no payment
provider are configured: production login and online payment are not available (see `backend/AUTH.md`,
`backend/PAYMENT.md`).

## Backend

- `GET /api/health/` — liveness, no dependencies.
- `GET /api/health/ready/` — checks PostgreSQL and Redis cache; `503` if either fails.
- Business API contracts: `backend/API.md` (conventions), `AUTH.md`, `CATALOG.md`, `CART.md`, `ORDERS.md`, `INVENTORY.md`, `PAYMENT.md`, `ADMIN.md`.
- DRF default permission is `IsAuthenticated` (secure by default; public endpoints must opt in).
- Object storage (S3-compatible) is a future integration boundary; DB will store image metadata only.

## Security notes

- Secure headers: Next.js (`next.config.ts`) and Django prod settings (HSTS, secure cookies, SSL redirect behind `X-Forwarded-Proto`).
- **CSRF strategy:** same-origin deployment behind Nginx, session auth with Django CSRF protection; `CSRF_TRUSTED_ORIGINS` lists allowed origins. CORS is closed unless `CORS_ALLOWED_ORIGINS` is set. Revisit when the auth flow is designed.
- `docker-compose.yml` publishes Nginx (`HTTP_PORT`, default 8080) on all host interfaces and PostgreSQL (host port 5433) on `127.0.0.1` only; Redis, backend and frontend are not published. Docker-published ports bypass host firewalls such as UFW, so on any internet-facing host use `docker-compose.vps.yml`, which also rebinds Nginx to `127.0.0.1`.
- HSTS stays at `0` until HTTPS is verified end-to-end.

## Manual commands

```powershell
# Frontend deps + lockfile (commit pnpm-lock.yaml afterwards)
cd frontend; pnpm install

# Backend deps (venv)
cd backend; python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements\dev.txt

# Full stack
copy .env.example .env      # then edit secrets
docker compose build
docker compose up -d
```

## Testing

```powershell
cd frontend; pnpm lint; pnpm typecheck; pnpm build
cd backend;  python manage.py check; pytest          # needs PostgreSQL via DATABASE_URL
cd e2e;      pnpm install; pnpm exec playwright install chromium; pnpm test   # stack must be up; sign-in, checkout and purchase-journey specs need a throwaway stack, and the helper/seeder also need `E2E_THROWAWAY_DB=1` (see e2e/README-purchase-journey.md)
```

## CI

`.github/workflows/ci.yml`: frontend (lint, typecheck, build) and backend (`check`, `check --deploy --fail-level WARNING` against `config.settings.prod` with throwaway values and no database contact, migrations check, pytest against a PostgreSQL service). Requires a committed `frontend/pnpm-lock.yaml`.

`.github/workflows/e2e.yml`: runs every spec in `e2e/tests` on a disposable Compose stack (empty volumes, removed with `down -v` at the end). It is triggered by pull requests and pushes to `main` that touch `e2e/**`, `backend/**`, `frontend/**`, `nginx/**`, `docker-compose.yml`, `.env.example` or the workflow itself, and manually. It is not a required check, and documentation-only changes do not trigger it. See `e2e/README-purchase-journey.md`.

## Development flow

Branch `agent/<number>-<scope>` from latest `main`, inspect before editing, run checks, commit, push, open PR. Never force-push shared branches.

## Production direction

CDN/WAF -> Nginx -> containers; managed PostgreSQL/Redis; S3-compatible storage + CDN for images (WebP/AVIF); error tracking, structured logs, metrics. Static files for Django admin still need a serving strategy (not done yet).
