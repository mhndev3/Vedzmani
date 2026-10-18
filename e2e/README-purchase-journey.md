# E2E suite and purchase journey (`tests/purchase-journey.spec.ts`)

## What runs in CI
`.github/workflows/e2e.yml` runs **every spec in `e2e/tests`** (purchase journey, checkout, catalog, storefront,
smoke, sign-in, auth-redirect) on a disposable Compose stack, on pull requests and on pushes to `main` that touch
`e2e/**`, `backend/**`, `frontend/**`, `nginx/**`, `docker-compose.yml`, `.env.example`
or the workflow, and on demand (`workflow_dispatch`; the workflow is on the default branch). Documentation-only changes
do not trigger it. It is **not** a required check. Each run:

1. starts from empty volumes (own Compose project name, fresh runner VM), runs `migrate`, seeds `seed_catalog.py` (with `E2E_THROWAWAY_DB=1`, see the safety guard below);
2. installs E2E dependencies with `pnpm install --frozen-lockfile` (`e2e/pnpm-lock.yaml`, pnpm pinned by
   `packageManager` in `e2e/package.json`, same package manager as `frontend/`);
3. runs `playwright test --reporter=github,json`;
4. `scripts/report-summary.mjs` reads the JSON report and **fails the job** if any test failed or was skipped, if the
   parsed count disagrees with Playwright's own stats, or if the purchase journey (must pass first time) or the
   checkout spec is missing or not passing. Flaky tests (pass only on retry) are reported as warnings;
5. removes the stack and its volumes (`down -v`).

Because the database is created empty for every run, tests that consume stock (the journey uses `e2e-hoodie-10`
black M, `checkout.spec.ts` uses others) cannot affect another run, and concurrent runs never share data. No reset
logic is needed in CI.

## Purchase journey coverage (one UI-driven test)
Storefront -> product list -> product detail -> size -> anonymous add-to-cart refused (no false success) -> real
OTP sign-in UI -> add to cart -> cart equals `GET /api/cart/` -> checkout with the five delivery fields -> "Order
placed" only after Django answers 201 -> `GET /api/orders/` shows one order whose total, SKU and unit price match the
server cart (`payment_status` is `unpaid`; no payment is taken) and the cart is empty. The order is created through
the UI; API calls only read state. Invalid input, server/network errors, double submit and stock conflicts live in
`checkout.spec.ts`.

## Authentication in tests (development only)
The OTP is read from the **test backend's log**: `config.settings.dev` uses the dev-only `ConsoleDelivery`
(`DEV OTP delivery: phone=... code=...`). That is not SMS. `checkout.spec.ts` uses `e2e_helper.py`, which creates a
real Django session with `force_login` on the throwaway database, because it exercises checkout rather than login;
everything after login (CSRF, cart, validation, stock, order creation) is real. Neither mechanism exists in production
settings, which refuse to boot with `ConsoleDelivery`.

### What real customer login still needs (owner decisions / work)
- Choose an SMS provider (open decision in `PROJECT_CONTROL.md`); no provider exists or is configured.
- Implement an `OTPDelivery` subclass for it (`backend/apps/accounts/delivery.py`) and set `OTP_DELIVERY_BACKEND` in the
  production environment. Until then production answers `503 otp_delivery_unavailable`, so **no real customer can sign
  in**.
- Verify it end to end with the provider's sandbox or an approved test number; keep OTP rate limits at production values.

## Safety guard (`E2E_THROWAWAY_DB`)
`seed_catalog.py` and `e2e_helper.py` write to whatever database `DATABASE_URL` points at: the seeder creates **active**
products with stock (they would appear on a real storefront), and the helper creates users and sessions and changes stock.
Both therefore refuse to run unless `E2E_THROWAWAY_DB=1` is set **and** the Django settings module is
`config.settings.dev` or `config.settings.test` (production settings are rejected).

- `E2E_THROWAWAY_DB=1` is **your confirmation that the database is disposable, not proof**. The scripts cannot verify it.
- The settings check cannot tell a throwaway database from a development one: the Compose backend runs
  `config.settings.dev` too. Before setting the flag, check the host and port of `DATABASE_URL` without printing the
  password (see `docs/VPS_DEVELOPMENT.md`, step 4).
- Set it only on the command that needs it. Never put it in a shell profile, a `.env` file or a shared environment.
- CI sets it only on the seed step and the Playwright step of the throwaway stack in `.github/workflows/e2e.yml`.

## Run locally
Prerequisites: Docker with Compose, Node 22+, pnpm (`corepack enable`), Python with `backend/requirements/dev.txt`
(for the checkout helper).

1. Follow `README-signin.md` steps 1-4 (throwaway `.env`, test-only `compose.test.yml` outside the repo, distinct
   project name, `migrate`, `seed_catalog.py`). Also publish Postgres and Redis on loopback in that override
   (see the `compose.test.yml` written by `.github/workflows/e2e.yml`).
2. Run:
```
cd e2e
pnpm install --frozen-lockfile
pnpm exec playwright install chromium
E2E_BASE_URL=http://localhost:8091 \
E2E_OTP_LOG_COMMAND="docker compose -p vedzmani-agenti logs --no-color backend" \
E2E_BACKEND_DIR=/abs/path/to/backend E2E_PYTHON=python E2E_THROWAWAY_DB=1 \
DJANGO_SETTINGS_MODULE=config.settings.dev DJANGO_SECRET_KEY=<same as the stack> \
DATABASE_URL=<same throwaway database as the stack> REDIS_URL=<same as the stack> \
pnpm exec playwright test
```
Without `E2E_OTP_LOG_COMMAND` / `E2E_BACKEND_DIR` the dependent tests are **skipped** (reported as skipped, never as
passed). Set `E2E_BROWSER_CHANNEL=chrome` only if Playwright's own browser cannot be downloaded.

## Cleanup
`docker compose -p <project> -f docker-compose.yml -f compose.test.yml down -v` removes the containers and the database
volume. Delete the throwaway `.env` and `compose.test.yml`. Never run a reset against a shared or production database.

## Known limitations
- A **local** rerun against the same database fails (stock already consumed): run `down -v` and reseed first. CI is
  unaffected because every run starts empty.
- Real SMS is unverified (see above); payment is not integrated; shipping is not included in `total`.
- The workflow is not a required check yet.
