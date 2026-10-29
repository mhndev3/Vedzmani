# Vedzmani — Project Control

## Project Status
- Repository: mhndev3/Vedzmani
- Default branch: main
- Architecture status: modular monolith implemented (Next.js + Django/DRF); the sections below record what exists
- Source of truth: GitHub
- Current phase: V1 readiness. The browse -> cart -> sign-in -> checkout -> order journey is covered by CI/E2E on a test stack; real OTP delivery and real payment are not integrated. A separate production Compose topology, WhiteNoise/static handling and production Nginx config now exist in `main`, but production deployment is not thereby approved or verified. Remaining blockers include live VPS/Cloudflare/firewall verification, off-host backup and rehearsed rollback, real OTP provider, payment integration, product/catalog data and owner decisions under "Architecture Decisions Pending External Product Inputs".
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
- Open: admin login needs the canonical `+989...` phone; admin static-file serving. (`stock_quantity` is no longer admin-editable: see Inventory Foundation below.)
## Order Creation (Agent 9, Session 1)
- `backend/apps/orders` (`Order` -> `OrderItem` -> `catalog.VariantSize`); contract and decisions in `backend/ORDERS.md`.
- `POST /api/orders/` (session auth + CSRF, authenticated users only, no request body) turns the caller's cart into an order in one transaction: locks the cart and the purchased `VariantSize` rows (`select_for_update`, pk order), revalidates availability/stock, snapshots name/SKU/price, decrements stock, clears the cart. Any unavailable or short line rejects the whole order with 409.
- Decided by the project owner: status field with the single value `pending` (no transitions), the database id is the only order identifier, no address/shipping/currency/tax (total = sum of line subtotals), customer phone snapshotted from the user.
- Open: guest checkout, status workflow/cancel/restock, payment, order number. Since this section was written, order list/detail (`GET /api/orders/`, `GET /api/orders/<id>/`), delivery details (Agent 11), the read-only order admin and the frontend checkout have been implemented; see the sections below.

## Inventory Foundation (Agent 10, Session 1)
- `backend/apps/inventory` (`InventoryAdjustment` audit rows); contract and decisions in `backend/INVENTORY.md`.
- Staff change stock only through `services.adjust_stock`: one transaction that validates, locks the `VariantSize` row (`select_for_update`), rejects negative stock, applies a guarded update and writes the audit row (who/why/when/how much).
- Admin: `VariantSize.stock_quantity` is read-only everywhere (new sizes start at 0). Adjustments are created at `/admin/inventory/inventoryadjustment/` (`inventory.add_inventoryadjustment`); history is append-only and read-only (`inventory.view_inventoryadjustment`), no change/delete even for superusers.
- Order checkout is unchanged: it still decrements under its own row lock and is recorded by the order, not as an adjustment.
- Open: automatic restock / order cancellation, an adjustments API or frontend, opening-balance backfill, low-stock alerts. `PROTECT` blocks deleting products/variants/sizes/staff that have history (deactivate instead).

## Checkout Delivery Details (Agent 11, Session 1)
- `POST /api/orders/` now requires Iranian delivery details in the body: `recipient_name`, `province`, `city`, `address`, `postal_code` (exactly 10 digits after Persian/Arabic-Indic digit normalization). Validated server-side before the transaction, so invalid input creates no order, changes no stock and leaves the cart intact. Contract: `backend/ORDERS.md`.
- Delivery details are snapshotted on `Order` (migration `orders/0002`, additive; pre-existing orders keep blank values). The delivery phone is the account phone (`customer_phone`); no recipient phone is accepted.
- `Order.payment_status` exists with the single server-owned value `unpaid`. **No payment provider is integrated; real payment is unavailable.** Boundary and requirements: `backend/PAYMENT.md`.
- `total` is the sum of line subtotals and **excludes shipping**; shipping cost/rules remain undecided (owner).
- Unchanged and documented risk: stock is still decremented at order creation, so unpaid orders can hold stock indefinitely (no expiry, cancellation or restock). Owner must decide the policy before online payment.
- **Production login is not available:** no SMS provider is selected. Docker Compose runs the backend with `config.settings.dev` (dev-only `ConsoleDelivery`); see `backend/AUTH.md`.
- **Order admin (read-only), `backend/apps/orders/admin.py`:** `Order` and `OrderItem` are inspect-only in Django Admin: no add, change or delete for anyone (superusers included), no actions, direct URLs and POSTs answer 403. The order list shows id, time, **masked** phone, statuses, total and item count. The full customer phone and the delivery snapshot (recipient, province, city, address, postal code) need the dedicated permission **`orders.view_order_pii`** (registered by a `post_migrate` handler, no model migration; granted to nobody by default; Django treats active superusers as holding every permission). Without it, PII is also kept out of search, query-string filters, sorting and related columns. Details, setup and limits: `backend/ADMIN.md`. **Status: implemented on branch `agent/order-admin-session-01`. Verified 2026-10-18 on Python 3.14.5 / Django 5.2.18 / pytest 8.4.2 against a disposable PostgreSQL 16 container: `manage.py check` and `makemigrations --check --dry-run` clean, `tests/test_admin_orders.py` 81 passed, full `pytest tests` 600 passed. Temporarily removing each of the main protections (lookup whitelist, read-only permissions, PII gate, non-sortable phone column, actions disabled, permission registration) made these tests fail.**
- Open / handed off: customer order list/detail pages, OTP provider, payment provider, shipping policy, unpaid-order stock policy. Frontend sign-in, add-to-cart, cart and checkout have since been implemented (see the sections below).

## Checkout Frontend (Agent C, Session 1; recovered and delivered by Agent G)
- Page `frontend/src/app/[locale]/checkout/page.tsx` (`/fa/checkout`, `/en/checkout`), form `frontend/src/components/checkout/CheckoutForm.tsx`, API client `frontend/src/lib/checkout/api.ts`, model `frontend/src/lib/checkout/model.ts`, dictionary `frontend/src/i18n/dictionaries/checkout.ts`. It uses the existing contract in `backend/ORDERS.md` and adds no endpoints, fields, fees or business rules.
- Behavior covered by the e2e tests: sign-in-required and empty-cart states; the cart total shown is the server's `GET /api/cart/` total; client-side validation sends no order request; `POST /api/orders/` carries only the five delivery fields plus `X-CSRFToken`; "Order placed" is shown only after Django answers 201; a network failure or server error never shows success (values are kept and a retry works); a stock conflict (409) keeps the entered values and refreshes the cart; duplicate submits are stopped by a synchronous in-flight guard plus a disabled submit button; Persian locale renders RTL.
- E2E: `e2e/tests/checkout.spec.ts` (10 tests; the two tests marked "(mocked response)" intercept the order POST, every other test calls the real backend). `e2e/e2e_helper.py` is **test-only**: no SMS provider exists, so it creates a real Django session with `force_login`. Run it only against a throwaway database seeded with `e2e/seed_catalog.py`, with `E2E_BACKEND_DIR`, `E2E_PYTHON` and `E2E_THROWAWAY_DB=1` set (the helper and the seeder refuse to run without the flag or outside `config.settings.dev`/`test`; the flag is the operator's confirmation, not proof of the database's identity), and keep `DATABASE_URL`, `REDIS_URL` and `DJANGO_SECRET_KEY` identical between the running server and the helper. `E2E_BROWSER_CHANNEL=chrome` drives an installed Chrome when Playwright's own browser download is blocked. **The real customer login flow is not verified.**
- Known e2e limitation (not fixed): the suite consumes seeded stock and the insufficient-stock test leaves `e2e-tee-06-black-m` at stock 1, so a second run against the same database fails in test setup (409) until stock is re-seeded.
- Verified by Agent G on 2026-10-14: `pnpm lint`, `pnpm typecheck` and `pnpm build` exit 0; all 10 checkout tests pass against local Django + PostgreSQL + Redis + Nginx + the Next.js production build (installed Chrome). With the in-flight guard and disabled button removed, the double-click test fails (the page shows "Please check before ordering again" instead of "Order placed").
- Not available / open: SMS/OTP provider; shipping fees (`total` excludes shipping); unpaid-order expiry and stock restoration. Since this section was written, the sign-in UI and cart UI exist, the cart links to `/checkout`, and `.github/workflows/e2e.yml` runs the checkout spec and the purchase journey in CI (on pull requests and pushes to `main` that touch `e2e/**`, `backend/**`, `frontend/**`, `nginx/**`, `docker-compose.yml`, `.env.example`; see `README.md`).

## Customer OTP Sign-in UI (Agent I, Session 1-2)
- Page frontend/src/app/[locale]/sign-in/page.tsx (/fa/sign-in, /en/sign-in, optional ?next=), form frontend/src/components/auth/SignInForm.tsx, client frontend/src/lib/auth/api.ts (on lib/browser-api.ts), error mapping lib/auth/errors.ts, redirect guard lib/auth/redirect.ts, copy i18n/dictionaries/auth.ts. It uses the existing contract in backend/AUTH.md; no backend change, no phone normalization or OTP logic in the frontend.
- Flow: phone -> POST /api/auth/otp/request/ -> 6-digit code -> POST /api/auth/otp/verify/ -> GET /api/auth/me/ confirms the session -> router.replace to the destination. Change number, resend (60 s display cooldown; Django's Retry-After replaces it on 429), already-signed-in visitors are forwarded. otp_attempts_exceeded and rate_limited (both 429) are shown differently. After a network loss on verify the UI asks /me before showing an error, since the session may already exist.
- ?next= accepts only same-origin, locale-prefixed paths (re-prefixed with the current locale; never //host, \host, schemes, control characters or the sign-in page). Default destination: /{locale}/profile.
- Entry points: sign-in links on the cart, checkout ("Sign in to continue" heading unchanged), profile and add-to-cart (401). Stale "not available yet" copy updated (fa/en).
- BrowserApiError now carries retryAfterSeconds (additive).
- Tests: e2e/tests/auth-redirect.spec.ts (unit), e2e/tests/signin.spec.ts; stack/instructions in e2e/README-signin.md. Real-OTP tests read the code from the TEST backend log (dev-only ConsoleDelivery).
- **Real SMS is NOT available:** no provider is configured; production returns 503 otp_delivery_unavailable, which the UI reports as "can't send codes right now". Real customer login remains unverified until a provider is chosen and tested.
- Known limitations / follow-ups: the language switcher drops the query string, so switching language on the sign-in page loses ?next= (falls back to profile); remember_me is not sent (session cookie only); no logout UI; no header sign-in link; checkout.spec.ts throws in its test.skip callback when E2E_BACKEND_DIR is unset (pre-existing); the other checkout tests were not run in this session.


## Authentication & Session Audit (Agent 6, Session 1)
- Audited the existing phone + OTP / Django session / CSRF boundary; details, effective session lifetimes and limits in `backend/AUTH.md` ("Audit"). No new endpoints, no API contract change, no frontend change.
- Fixed: an OTP-only session for an `is_staff` phone used to open `/admin/` (bypassing the staff password); admin now requires the password form (`apps/accounts/admin_site.py`, `backend/ADMIN.md`). Fixed: any delivery-adapter exception now yields the documented 503 and expires the unsent code.
- Tests: `test_accounts_admin_gate.py`, `test_accounts_delivery_failures.py`, `test_accounts_session_security.py` (isolated PostgreSQL, in-memory cache, mocked delivery).
- **Real SMS/OTP delivery is still NOT available and live-provider verification is BLOCKED** (no provider chosen). Open: purge jobs for expired sessions and `OTPChallenge` rows, `AUTH_TRUSTED_PROXY_COUNT` verification behind the real proxy chain, 14-day server-side lifetime of browser-session logins (owner may want a shorter value).
### Authentication & Session, Session 2 (Agent 6)
- Added `manage.py purge_expired_auth_data` (`apps/accounts/cleanup.py`): dry-run by default, batched with `SKIP LOCKED`, expired sessions always eligible, OTP rows only with an explicit `--otp-retention-days` (owner policy, no default). **It is NOT scheduled: no scheduler exists in any branch; the owner must choose one (cron / compose sidecar / Celery beat).**
- Hardened `get_client_ip`: the trusted `X-Forwarded-For` entry must be a valid IP; IPv6 keys collapse to /64; IPv4-mapped IPv6 to IPv4. Local proof of the Nginx side: `scripts/proxy-chain-probe/run.ps1`.
- **Unverified (needs VPS/Cloudflare evidence, see `backend/AUTH.md`):** which Nginx/settings production runs, whether `cloudflare-realip.conf` is populated, whether the backend is reachable only through Nginx.