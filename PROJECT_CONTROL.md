# Vedzmani — Project Control

## Project Status
- Repository: mhndev3/Vedzmani
- Default branch: main
- Architecture status: greenfield
- Source of truth: GitHub
- Current phase: Foundation

## Product Scope
Vedzmani is a production-grade fashion e-commerce platform. The source requirements document is the authoritative product-scope input. It covers storefront navigation, search, cart, favorites, categories, filters, product variants, reviews, OTP/profile, collections, inventory, homepage management, and an admin panel.

## Target Architecture
- Architecture style: Modular Monolith
- Language: TypeScript (strict)
- Application: Next.js + React
- UI: Tailwind CSS + shadcn/ui
- Validation: Zod
- Database: PostgreSQL
- ORM: Drizzle ORM
- Cache / rate limiting / short-lived state: Redis
- Reverse proxy: Nginx in production topology
- Containerization: Docker; Docker Compose for local development
- Object storage: S3-compatible storage
- Delivery: CDN/WAF in front of origin
- Background jobs: Redis-backed worker/queue where asynchronous work is justified
- Testing: Vitest + Playwright
- CI/CD: GitHub Actions
- Observability: error tracking + structured logs + metrics

## Core Architecture Rules
1. Prefer server-rendered/server components and minimal client JavaScript.
2. Client components are used only when browser interactivity requires them.
3. PostgreSQL is the source of truth for business-critical state.
4. Redis is never the authoritative source for orders, payments, or inventory.
5. Product inventory is variant-aware: product -> color/size variant -> inventory.
6. Product images belong to variants where color-specific imagery is required.
7. Images must be optimized and delivered through object storage/CDN; WebP is required by product requirements, and AVIF may be generated when supported.
8. Do not introduce microservices unless a measured requirement justifies extraction.
9. Do not introduce Kubernetes, Kafka, Elasticsearch/OpenSearch, GraphQL, or additional databases without an explicit architecture decision.
10. Performance decisions must be measured; avoid infrastructure for infrastructure's sake.
11. Database access must use explicit indexes and optimized queries.
12. Business-critical inventory/order changes require database transactions and concurrency-safe logic.
13. Authentication and authorization are separate concerns; admin access must be role/permission controlled.
14. No agent may silently change the agreed stack or architecture.
15. No agent may leave broken builds, failing tests, uncommitted work, or half-finished assigned scope.

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

## Agent 1 Foundation Scope
Agent 1 establishes the repository foundation only. It must not implement product features, database business models, authentication flows, cart, checkout, admin CRUD, or storefront feature logic. Its output must be a clean, buildable, containerized development foundation that later agents can safely extend.
