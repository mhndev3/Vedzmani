# API contract (cross-cutting)

Per-domain details live in `AUTH.md`, `CATALOG.md`, `CART.md`, `ORDERS.md`. This file records what is common
to all of `/api/` and the known inconsistencies. Pinned by `tests/test_api_contract.py`.

## Transport
- JSON everywhere. Routes: `/api/` (health), `/api/auth/`, `/api/catalog/`, `/api/cart/`, `/api/orders/`.
- Django serves `/api/` and `/admin/`; nginx sends everything else to Next. Next has **no** `/api` rewrites, so
  browser-side calls to `/api/...` only work behind nginx (or a dev proxy), never against `next dev` alone.
- Money is a Decimal rendered as a **string** (whole units). Totals, prices and stock always come from the server.

## Error envelope
`{"error": {"code": str, "message": str, "details"?: {field: [{"code","message"}]}}}`
- 400 `validation_error` (with `details`), 401 `not_authenticated` (+ `WWW-Authenticate: Session`),
  403 `permission_denied` / `csrf_failed`, 404, 405, 409 domain conflicts (e.g. `insufficient_stock`).
- Unknown `/api/*` routes and malformed path ids (e.g. `/api/cart/items/abc/`) return the envelope with 404 `not_found`.
  Non-`/api/` 404s keep Django's default page.

## Auth / CSRF
- Session cookie auth. Call `GET /api/auth/csrf/` once, then send the token as `X-CSRFToken` on every unsafe request.
- A missing/invalid token is always 403 `csrf_failed` (message fixed; the reason is not echoed).
- `GET /api/auth/me/` is `Cache-Control: no-store`-class (never cacheable); cart and orders are the same.

## Pagination
- Catalog listing: `{count, next, previous, results}`. Orders list: a plain array (not paginated).

## Known inconsistencies / open ambiguities (documented, not changed)
1. **404 `code` differs by source**: `error` (Django `Http404`, documented in `ORDERS.md`) vs `not_found` (DRF
   `NotFound`, unknown routes). Clients must not branch on the 404 code; use the status.
2. Cart `POST` also accepts form-encoded bodies, not only JSON. Clients should send JSON.
3. `MEDIA_CDN_BASE_URL` is empty by default and absent from compose/`.env` examples, so image URLs are
   origin-relative (`/<key>`) and resolve against the Next origin. Set it (or route them) before launch.
4. Orders contract will change when `origin/agent/11-checkout-session-01` merges (POST no longer takes an
   empty body). Frontend must not rely on the empty-body form.
5. Catalog `q`/`category` have server-side length caps; the frontend does not pre-validate them and shows its
   retry state on a 400.
