# Vedzmani

Production-grade fashion e-commerce platform. **Modular monolith**: Next.js frontend + Django/DRF backend.
Authoritative contract: [`PROJECT_CONTROL.md`](PROJECT_CONTROL.md). This README covers the **foundation only** — no business features exist yet.

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
backend/    Django project (config/, apps/core health endpoints, tests/, requirements/)
frontend/   Next.js App Router, TypeScript strict, Tailwind v4, shadcn-compatible
e2e/        Playwright smoke tests (separate package)
nginx/      Reverse-proxy config
.github/    CI workflow
docker-compose.yml, .env.example
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

## Backend

- `GET /api/health/` — liveness, no dependencies.
- `GET /api/health/ready/` — checks PostgreSQL and Redis cache; `503` if either fails.
- DRF default permission is `IsAuthenticated` (secure by default; public endpoints must opt in).
- Object storage (S3-compatible) is a future integration boundary; DB will store image metadata only.

## Security notes

- Secure headers: Next.js (`next.config.ts`) and Django prod settings (HSTS, secure cookies, SSL redirect behind `X-Forwarded-Proto`).
- **CSRF strategy:** same-origin deployment behind Nginx, session auth with Django CSRF protection; `CSRF_TRUSTED_ORIGINS` lists allowed origins. CORS is closed unless `CORS_ALLOWED_ORIGINS` is set. Revisit when the auth flow is designed.
- Only Nginx publishes a host port in Compose.
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
cd e2e;      pnpm install; pnpm exec playwright install chromium; pnpm test   # stack must be up
```

## CI

`.github/workflows/ci.yml`: frontend (lint, typecheck, build) and backend (`check`, migrations check, pytest against a PostgreSQL service). Requires a committed `frontend/pnpm-lock.yaml`.

## Development flow

Branch `agent/<number>-<scope>` from latest `main`, inspect before editing, run checks, commit, push, open PR. Never force-push shared branches.

## Production direction

CDN/WAF -> Nginx -> containers; managed PostgreSQL/Redis; S3-compatible storage + CDN for images (WebP/AVIF); error tracking, structured logs, metrics. Static files for Django admin still need a serving strategy (not done yet).
