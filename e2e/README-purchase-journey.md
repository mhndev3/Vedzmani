# Purchase journey e2e (`tests/purchase-journey.spec.ts`)

**Status: UNVERIFIED.** The spec and `.github/workflows/e2e.yml` were written in an environment where
package and image registries were unreachable, so neither has been executed. Treat any failure as
expected until the first real run.

What it covers (one UI-driven test): storefront -> product list -> product detail -> size -> anonymous
add-to-cart refused (no false success) -> real OTP sign-in UI -> add to cart -> cart equals `GET /api/cart/`
-> checkout with the five delivery fields -> "Order placed" only after Django answers 201 -> `GET /api/orders/`
shows one order whose total, SKU and unit price match the server cart and which leaves the cart empty.
Invalid input, server/network errors, double submit and stock conflicts are already covered by
`checkout.spec.ts`; this spec does not repeat them.

## Prerequisites
Docker with Compose, Node 22+, and the isolated stack from `README-signin.md` (steps 1-4: throwaway `.env`,
test-only `compose.test.yml` kept outside the repo, distinct project name, `migrate`, then `seed_catalog.py`).
Never run this against a stack with real data.

## Environment variables (names and safe examples)
- `E2E_BASE_URL=http://localhost:8091` (the isolated Nginx)
- `E2E_OTP_LOG_COMMAND="docker compose -p vedzmani-agenti logs --no-color backend"` (reads the dev-only
  `ConsoleDelivery` log; without it the test is skipped, which Playwright reports as skipped, not passed)
- `E2E_BROWSER_CHANNEL=chrome` only if Playwright's own browser cannot be downloaded

## Run
```
cd e2e
npm install            # no lockfile exists yet for e2e/
npx playwright install chromium
E2E_BASE_URL=http://localhost:8091 \
E2E_OTP_LOG_COMMAND="docker compose -p vedzmani-agenti logs --no-color backend" \
npx playwright test tests/purchase-journey.spec.ts
```

## Cleanup
`docker compose -p vedzmani-agenti -f docker-compose.yml -f compose.test.yml down -v` removes the containers
and the database volume. Delete the throwaway `.env` and `compose.test.yml`.

## Known limitations
- Consumes one unit of `e2e-hoodie-10` black M; re-seed a fresh database before running again.
- Real SMS is not available, so this proves nothing about production login.
- The CI workflow is manual-only and unverified; `e2e/` still has no lockfile.
