# Vedzmani — Project Control

## Project Status
- Repository: mhndev3/Vedzmani
- Default branch: main
- Architecture status: greenfield / foundation reset
- Source of truth: GitHub
- Current phase: Foundation — Python/Django backend reset
- V1 deadline constraint: 18 days from project restart

## Product Scope
Vedzmani is a production-grade fashion e-commerce platform. The source requirements document is the authoritative product-scope input. It covers storefront navigation, search, cart, favorites, categories, filters, product variants, reviews, OTP/profile, collections, inventory, homepage management, and an admin panel.

## Target Architecture
- Architecture style: Modular Monolith
- Frontend language: TypeScript (strict)
- Frontend application: Next.js + React
- Frontend UI: Tailwind CSS + shadcn/ui
- Backend language: Python
- Backend application: Django
- API layer: Django REST Framework (DRF)
- Backend validation/serialization: DRF serializers + explicit domain validation; Pydantic only where a concrete boundary requires it
- Database: PostgreSQL
- ORM: Django ORM
- Cache / rate limiting / short-lived state: Redis
- Background jobs: Celery with Redis broker/backend where asynchronous work is justified
- Reverse proxy: Nginx in production topology
- Containerization: Docker; Docker Compose for local development
- Object storage: S3-compatible storage
- Delivery: CDN/WAF in front of origin
- Testing: Pytest/pytest-django + Playwright
- CI/CD: GitHub Actions
- Observability: error tracking + structured logs + metrics

## Core Architecture Rules
1. Prefer server-rendered/server components and minimal client JavaScript in the Next.js frontend.
2. Client components are used only when browser interactivity requires them.
3. Django/DRF is the authoritative backend and owns business logic, API behavior, authentication/authorization, orders, inventory, pricing, and integration boundaries.
4. PostgreSQL is the source of truth for business-critical state.
5. Redis is never the authoritative source for orders, payments, or inventory.
6. Product inventory is variant-aware: product -> color/size variant -> inventory.
7. Product images belong to variants where color-specific imagery is required.
8. Images must be optimized and delivered through object storage/CDN; WebP is required by product requirements, and AVIF may be generated when supported.
9. Keep the system as a modular monolith: Next.js frontend + Django/DRF backend. Do not split Django domain modules into microservices.
10. Do not introduce microservices unless a measured requirement justifies extraction.
11. Do not introduce Kubernetes, Kafka, Elasticsearch/OpenSearch, GraphQL, or additional databases without an explicit architecture decision.
12. Performance decisions must be measured; avoid infrastructure for infrastructure's sake.
13. Database access must use explicit indexes and optimized queries.
14. Business-critical inventory/order changes require database transactions and concurrency-safe logic.
15. Authentication and authorization are separate concerns; admin access must be role/permission controlled.
16. External payment, SMS/OTP, shipping, storage, and notification providers must be isolated behind integration boundaries so V1 can connect providers without rewriting domain logic.
17. No agent may silently change the agreed stack or architecture.
18. No agent may leave broken builds, failing tests, uncommitted work, or half-finished assigned scope.

## Performance Budget (initial targets)
- LCP: target <= 2.5s on key storefront pages
- INP: target <= 200ms
- CLS: target <= 0.1
- Minimize JS shipped to the browser.
- Avoid N+1 queries.
- Prefer CDN/browser caching and application caching where correctness permits.
- Use lazy loading for non-critical media.
- Reserve image dimensions to avoid layout shift.
- Production images must be responsive and optimized.

## Git / Agent Workflow
- main is the stable integration branch.
- Every agent works from the latest main.
- Agents 1-6 may work on the primary development machine; agents 7-11 must clone/pull from GitHub and treat GitHub as the source of truth.
- Prefer agent/<number>-<scope> branches and PRs into main.
- Never force-push shared branches.
- Every session must end with tests/build verification, a commit, and push.
- A session is not complete until its checkpoint is reproducible from GitHub.
- Agents must inspect existing work before modifying it and must not overwrite unrelated changes.

## Session Contract
Every session:
1. Inspect git status and current branch.
2. Pull/fetch latest main.
3. Read PROJECT_CONTROL.md and relevant project docs.
4. Inspect the current implementation before editing.
5. Implement only the assigned session scope.
6. Run relevant tests/typecheck/lint/build.
7. Fix failures caused by the session.
8. Commit with a descriptive message.
9. Push the branch.
10. Report: files changed, tests run, commit SHA, known issues, and exact next-session handoff.

## Definition of Done
A feature/session is Done only when:
- assigned scope is implemented,
- types are valid,
- relevant tests pass,
- lint/format checks pass,
- production build passes when applicable,
- no unrelated behavior was broken,
- documentation/configuration required by the change exists,
- changes are committed and pushed,
- the repository is left in a clean, reproducible state.

## Architecture Decisions Pending External Product Inputs
These are intentionally not invented:
- payment gateway/provider
- SMS/OTP provider
- shipping provider and pricing rules
- WhatsApp/support integration depth
- return/refund workflow
- discount/promotion rules
- exact order state machine
- production hosting/provider and exact storage/CDN vendor

These must be selected before implementing dependent production integrations.

## V1 Delivery Constraint
V1 must be usable for taking customer orders within the 18-day delivery window. V1 does not need every advanced feature or polished edge case, but the core browse -> variant selection -> cart -> customer/order details -> order creation -> inventory flow must be deliverable, testable, secure enough for launch preparation, and ready for payment/API integrations. Prefer the smallest solid implementation that unblocks ordering over nonessential architecture or polish.

## Agent 1 Foundation Scope
Agent 1 establishes the repository foundation only. The foundation is a Next.js frontend + Django/DRF backend modular monolith. It must not implement product features, database business models, authentication flows, cart, checkout, admin CRUD, or storefront feature logic. Its output must be a clean, buildable, containerized development foundation that later agents can safely extend.

## Backend Stack Decision
The backend stack is now explicitly **Python + Django + Django REST Framework**. The previous Next.js/TypeScript backend, Drizzle ORM, and Vitest-only backend foundation are superseded. PostgreSQL remains the primary database, Django ORM is the backend ORM, Redis remains the cache/short-lived-state layer, and Celery may be introduced for justified asynchronous jobs.

## Frontend/Backend Boundary
Next.js is the frontend/application presentation layer. Django/DRF owns authoritative business logic and API contracts. Do not duplicate business rules between frontend and backend. The frontend communicates with Django through versionable HTTP APIs; the exact API versioning strategy should remain simple for V1 and must not introduce unnecessary gateway/microservice complexity.

## Auth Foundation (Agent 3, Session 1)
- Custom `accounts.User` (phone = identifier, canonical `+989XXXXXXXXX`; Django-native is_staff/is_superuser/groups/permissions) and `OTPChallenge` (HMAC-hashed codes) live in `backend/apps/accounts`.
- Authentication is Django session auth (DB-backed sessions, CSRF enforced); no JWT. Contract: `backend/AUTH.md`.
- OTP delivery is isolated behind `OTP_DELIVERY_BACKEND`; no SMS provider is chosen yet, so the production default refuses to send (503).
- Behind Nginx set `AUTH_TRUSTED_PROXY_COUNT=1` (compose does) so per-IP rate limits use the real client IP.

## Cart Backend (Agent 7, Session 1)
- `backend/apps/cart` (`Cart` 1:1 user, `CartItem` -> `catalog.VariantSize`); contract and decisions in `backend/CART.md`.
- Session-authenticated, user-scoped, server-priced (`Product.current_price`), **never touches stock**; checkout must re-validate inventory.
- Guest cart, orders/checkout, frontend wiring and cart limit confirmation (`CART_MAX_ITEM_QUANTITY`, `CART_MAX_LINES`) are open follow-ups.

## Django Admin (Agent 8, Session 1)
- Built-in Django admin at `/admin/` (session auth + `is_staff` + stock model permissions; no custom RBAC, no custom dashboard). Details and caveats: `backend/ADMIN.md`.
- Phone-based user admin; catalog admin (variant page edits sizes/stock + images); cart admin is view-only with masked owners; `OTPChallenge` is deliberately not registered.
- Open: admin login needs the canonical `+989...` phone; `stock_quantity` is admin-editable until the inventory module exists; admin static-file serving.
