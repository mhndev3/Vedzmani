# Vedzmani V1 Readiness Audit

Audit date: 2026-10-14. Author: Agent A (coordinator / integration analyst). Docs-only change; no product code touched.
Legend: **[V]** verified by running it or by reading the cited source; **[A]** assumption / not verified.

## 1. Repository and commit inspected
- Repo `mhndev3/Vedzmani`, `origin/main` = `ab518503d464635bc4543636da2687c237021641` ("Merge pull request #12 from agent/11-checkout-session-01"). **[V]**
- PRs #1-#13 are all merged; none are open (GitHub REST API listing + `git ls-remote refs/pull/*`). PR #12 (checkout delivery details + payment boundary) and PR #13 (API error-contract alignment) are ancestors of `main`. **[V]**
- Base for this report: branch `agent/A-v1-readiness-audit` created at `ab51850` (identical to `origin/main`, clean tree).

## 2. CI status
- GitHub check-runs for `ab51850`: `backend` completed/success, `frontend` completed/success. **[V]**
- `.github/workflows/ci.yml` runs: frontend `pnpm lint`, `typecheck`, `build`; backend `manage.py check`, `makemigrations --check --dry-run`, `pytest` on PostgreSQL 16 (Python 3.13). **Playwright e2e is not run in CI.** **[V]**
- Local re-run on current `main` (Windows, Python 3.14.6, throwaway PostgreSQL 16 container): `manage.py check` clean; `makemigrations --check --dry-run` "No changes detected"; `pytest` **519 passed**; frontend `pnpm lint` and `pnpm typecheck` exit 0. **[V]**
- Not run by this audit: `pnpm build`, Playwright, Docker Compose full stack, Redis-backed paths (rate limits). **[A]**

## 3. Readiness by area

| Area | Status | Evidence |
|---|---|---|
| Catalog / product data (API) | Implemented and verified | `GET /api/catalog/products/`, `/products/<slug>/`, `/filters/`; `backend/CATALOG.md`; 519-test suite green incl. query-count tests |
| Product detail + variant selection (UI) | Partially implemented | `frontend/src/app/[locale]/products/[slug]/page.tsx`: color via `?color=`, images, in-stock flag; "Add to cart" is a disabled placeholder (`t.product.addToCartUnavailable`); no size picker wired to `variant_size_id` |
| Authentication / OTP (API) | Implemented and verified (dev only) | `/api/auth/csrf|otp/request|otp/verify|me|logout/`; `backend/AUTH.md` |
| OTP in production | Blocked by a product/provider decision | No SMS provider; default `UnconfiguredDelivery` answers `503 otp_delivery_unavailable`; compose uses `config.settings.dev` + `ConsoleDelivery` |
| Sign-in UI | Missing | Only `profile/page.tsx` calls `/api/auth/me/`; no OTP request/verify page |
| Cart (API) | Implemented and verified | `/api/cart/`, `/api/cart/items/`, `/api/cart/items/<id>/`; `backend/CART.md`; server-priced, never touches stock |
| Cart (UI) | Missing | No cart page or add-to-cart call anywhere in `frontend/src` |
| Guest cart / guest checkout | Missing | Cart and orders require session auth (401 when anonymous) |
| Delivery details + order creation (API) | Implemented and verified | `POST /api/orders/` (5 Iranian delivery fields, `postal_code` 10 digits); `GET /api/orders/`, `/api/orders/<id>/`; `backend/ORDERS.md`; `tests/test_orders_api.py`, `test_orders_checkout_details.py`, `test_orders_read_api.py`, `test_orders_postal_code.py`, `test_orders_migration.py` |
| Checkout / orders (UI) | Missing | No checkout, confirmation or orders pages |
| Inventory consistency | Implemented and verified (concurrency) | Row locks in PK order, guarded decrement, DB CHECK stock >= 0; `apps/inventory` audit trail; thread-based tests (`test_last_unit_cannot_be_oversold`, `test_concurrent_orders_over_same_items_do_not_deadlock_or_miscount`, `test_concurrent_removals_never_oversell`) pass |
| Cancellation / restock / unpaid-order policy | Missing | Stock is decremented at creation and nothing returns it (`ORDERS.md`, `PAYMENT.md`); `Order.status` has the single value `pending` |
| Admin: catalog, users, carts, inventory | Implemented and verified | `/admin/`; `backend/ADMIN.md`; `tests/test_admin_*.py`, `test_inventory_admin.py` |
| Admin: orders | Missing | No `backend/apps/orders/admin.py`; grep for Order registration in all `admin.py` files finds none. Staff cannot view/process orders. |
| Payment-provider boundary | Blocked by a product/provider decision | `Order.payment_status` fixed at `unpaid`; no provider, no adapter; requirements in `backend/PAYMENT.md` |
| Shipping cost | Blocked by a product/provider decision | `Order.total` excludes shipping; no fee/courier model |
| Automated tests | Implemented and verified (backend) / partially (frontend, e2e) | Backend 519 passing; e2e specs `e2e/tests/{smoke,catalog,storefront}.spec.ts` exist but are not in CI and were not run here |
| Production deployment | Partially implemented / blockers | See section 6 |

## 4. Integration contracts and dependencies (for Agent B and cart/checkout work)
Common rules (`backend/API.md`, pinned by `tests/test_api_contract.py`):
- JSON; money is a whole-unit Decimal **string**; currency undecided. Errors: `{"error":{"code","message","details?"}}`.
- Session cookie auth. `GET /api/auth/csrf/` then send `X-CSRFToken` on every unsafe request; missing/invalid -> `403 csrf_failed`.
- Browser calls to `/api/...` only work behind nginx or a dev proxy; Next has **no** `/api` rewrites (`API.md`). Agent B and anyone building cart/checkout UI must run through compose/nginx or add a dev proxy.
- 404 `code` differs by source (`error` vs `not_found`): branch on HTTP status, not code.

Routes to consume:
- Listing `GET /api/catalog/products/` params `search, category, collection, color, size, min_price, max_price, in_stock, sort, page, page_size`; envelope `{count,next,previous,results}`; item `{id,name,slug,price,sale_price,category,in_stock,image,colors[]}`.
- Detail `GET /api/catalog/products/<slug>/`: `colors[].sizes[].id` **is the `variant_size_id`** the cart needs; stock is exposed only as `in_stock`.
- Cart `POST /api/cart/items/ {variant_size_id, quantity?}`; `PATCH /api/cart/items/<item_id>/ {quantity}`; every cart call returns `{items[], item_count, total_quantity, total, has_issues}` with per-line `availability` (`available | insufficient_stock | unavailable`). Limits `CART_MAX_ITEM_QUANTITY=10`, `CART_MAX_LINES=50` are unconfirmed defaults.
- Order `POST /api/orders/` body `{recipient_name, province, city, address, postal_code}` -> `201` order with `status:"pending"`, `payment_status:"unpaid"`; 409 `item_unavailable` / `insufficient_stock`, 400 `empty_cart` / `validation_error`. `total` excludes shipping and must not be shown as a final price. Reads: `GET /api/orders/` (plain array, not paginated), `GET /api/orders/<id>/` (404 for others' orders).
- Frontend files that exist: `frontend/src/lib/api.ts` (`apiGet`), `lib/catalog.ts`, `components/storefront/catalog/*`, i18n `en.ts`/`fa.ts`. Cart/checkout/auth UI needs new files plus dictionary keys in both languages.

## 5. Blocking decisions (owner / product)
1. SMS/OTP provider (production login is impossible without it).
2. Payment approach for V1: online provider vs manual/cash-on-delivery confirmation; currency/display unit.
3. Shipping cost rules (changes the payable amount; needs a separate field, not a change to `total`).
4. Unpaid-order stock policy (expiry vs cancel + restock) and the order status state machine.
5. Confirm cart limits; whether guest checkout is required for V1 (currently login-only).
6. Production hosting, object storage/CDN vendor (image URLs are origin-relative until `MEDIA_CDN_BASE_URL` is set).

## 6. Production deployment blockers
- `docker-compose.yml` runs the backend with `config.settings.dev`; there is no production compose/topology. **[V]**
- `backend/Dockerfile` CMD runs `gunicorn` only: no `migrate` and no `collectstatic` step anywhere in compose or the image. **[V]**
- `nginx/default.conf` proxies `/api/`, `/admin/`, `/` only; no `/static/` or media location, and `STATIC_ROOT` has no serving strategy, so Django admin assets will not load behind nginx (README and `ADMIN.md` already note this). **[V]**
- `MEDIA_CDN_BASE_URL` empty and absent from env examples (`API.md` item 3). **[V]**
- No observability (error tracking/metrics) or Celery wiring present; Redis is used for cache/rate limits only. **[V]**

## 7. Prioritized remaining tasks (dependency-ordered)
Owners are suggestions by role; assign to actual agents A-E as the project owner sees fit.

| # | Task | Depends on | Suggested owner |
|---|---|---|---|
| 0 | Decide items 1-4 in section 5 | none | Project owner |
| 1 | Order admin: staff-only list/detail, restrict delivery PII, read-only fields | none | Backend agent |
| 2 | Deploy fixes: migrate on start, static serving for admin, prod settings compose profile, `MEDIA_CDN_BASE_URL` | none | Backend/infra agent (touches shared root config: coordinate) |
| 3 | Sign-in UI (OTP request/verify, CSRF bootstrap, logout) against dev `ConsoleDelivery` | none (prod needs #0.1) | Frontend agent |
| 4 | Product page: size selection + working add-to-cart (`variant_size_id`) | #3; Agent B's catalog/product pages merged | Agent B (owns these files) |
| 5 | Cart page (quantities, availability warnings, totals from server) | #3, #4 | Frontend agent |
| 6 | Checkout form (5 fields, server validation errors) + order confirmation and "my orders" pages | #5 | Frontend agent |
| 7 | Order status workflow, cancel + restock service and admin action | #0.4, #1 | Backend agent |
| 8 | Payment adapter per `PAYMENT.md` (or manual confirmation flow) | #0.2, #7 | Backend agent |
| 9 | Shipping cost field and rules | #0.3 | Backend agent |
| 10 | Playwright order path (sign-in -> cart -> checkout) and add e2e to CI | #3-#6 | QA/e2e agent |
| 11 | Sync `PROJECT_CONTROL.md` and README with reality (see section 8) | none | Coordinator |

## 8. Documentation drift found
- `PROJECT_CONTROL.md` still lists order list/detail as "Open" (merged in PR #10) and the Order Creation section predates delivery details.
- `README.md` says "no business features exist yet" and "foundation only".
- `backend/ORDERS.md` header says Sessions 1-2 only although Agent 11 added delivery details to it.

## 9. Risks to an order-capable V1
1. **No customer can place an order today**: no sign-in, add-to-cart, cart or checkout UI, and production OTP cannot send. Highest risk to the 18-day deadline.
2. **Stock leakage**: unpaid or abandoned orders keep stock decremented with no way to restock except manual inventory adjustments.
3. **Staff cannot see orders** (no order admin), so orders could not be fulfilled even if placed.
4. Money semantics (currency, shipping) undecided; displaying `total` as a final price would be wrong.
5. Deployment path is dev-only; admin assets and migrations are not handled in the container topology.
6. No e2e in CI: UI-to-API integration (CSRF, cookies behind nginx) is unverified end to end. **[A]** An ignored local artifact `e2e/test-results/...profile-is-sign.../error-context.md` suggests a profile sign-in e2e once failed locally; not investigated.
7. Cross-agent conflict risk: product page edits (add-to-cart) overlap Agent B's files.

## 10. Recommended next steps
1. Owner answers the section 5 decisions (OTP provider and payment approach first).
2. Start tasks 1, 2 and 3 in parallel: they are unblocked and touch different files.
3. Agent B finishes catalog/product pages, then hands off a merged `main` before task 4.
4. Run Playwright against the compose stack once tasks 3-6 land, and add it to CI.
