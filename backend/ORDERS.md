# Orders API (Agent 9, Sessions 1–2)

App: `backend/apps/orders`. PostgreSQL is the source of truth. An authenticated user can **create** an order from
their cart (Session 1) and **read** their own orders (Session 2). Nothing else about the order lifecycle exists
yet (see "Not implemented").

```
User ─< Order ─< OrderItem >─ catalog.VariantSize        (OrderItem unique (order, variant_size); quantity > 0)
```

## Contract
Both endpoints use the same auth: **Django session cookie (same as `AUTH.md`); anonymous → `401 not_authenticated`.**
The owner is always `request.user`; no user id is ever accepted from the client (e.g. `?user=` is ignored). Every
response (success and error) is `Cache-Control: no-store, private` (`never_cache`). Methods other than the ones
listed per endpoint → `405`.

### `POST /api/orders/` — create (Session 1; delivery details added by Agent 11)
JSON in, JSON out. Needs the CSRF header `X-CSRFToken` (`GET /api/auth/csrf/`), otherwise `403 csrf_failed`.
The order is built from `request.user`'s own cart. No user id, item list, price, status, payment status or total is
ever accepted from the client. Responses are `Cache-Control: no-store, private`.

**Request body (required)** — the Iranian delivery details, all strings:

| field | rule |
|---|---|
| `recipient_name` | required, trimmed, 1–120 characters |
| `province` | required, trimmed, 1–60 characters (free text, no master list) |
| `city` | required, trimmed, 1–60 characters (free text, no master list) |
| `address` | required, trimmed, 1–255 characters |
| `postal_code` | required; after trimming and converting Persian/Arabic-Indic digits to ASCII it must be **exactly 10 digits** (`apps/orders/postal_code.py`). Separators, letters and other digit scripts are rejected. No stricter national rule is applied (none was provided). |

JSON numbers, booleans and `null` are rejected for every field (a number would lose a leading zero). Text fields are
single-line: control characters (newline, tab, NUL, ...) are rejected **anywhere in the submitted value, including a
leading or trailing one** (they are checked before trimming, so they are never silently removed); ordinary spaces around
the value are trimmed, and a value that is only whitespace is `blank`. Zero-width non-joiner (needed for Persian) is
allowed. There is no `country` field (the V1 market is Iran). **There is no phone field**: see "Delivery phone".
Any other key in the body (`user`, `total`, `status`, `payment_status`, `phone`, `items`, ...) is ignored and never read.

Success `201`:
```
{ id, status: "pending", payment_status: "unpaid", customer_phone,
  recipient_name, province, city, address, postal_code,
  total, created_at,
  items: [{ id, variant_size_id, product_name, color_name, size_label, sku, unit_price, quantity, subtotal }] }
```
`id` is the database id and the only order identifier (no separate public order number yet). Money is a whole-unit
Decimal rendered as a string, like the catalog and cart (currency still undecided).

**`total` excludes shipping.** It is the sum of the line subtotals. No shipping fee, free-shipping rule, courier or
delivery estimate exists (decision pending with the owner), so `total` is **not** a final delivered price and the UI
must not present it as one. Adding shipping later must introduce a separate field rather than silently change `total`.

### `GET /api/orders/` — list own orders (Session 2)
`200` with a plain JSON **array** of orders in exactly the `201` shape above, **newest first** (`created_at` desc,
then `id` desc). `[]` when the user has none. **Not paginated** (V1 order volume per user is small; if pagination is
adopted later the shape would change to the catalog's `count/next/previous/results`). Items come back in id order.
Only `GET` is allowed here besides `POST`; `PUT`/`PATCH`/`DELETE` → `405`.

### `GET /api/orders/<id>/` — retrieve one own order (Session 2)
`200` with a single order object (same shape). `<id>` is the database id (integer). The order is looked up inside the
caller's own orders only, so an order that **belongs to someone else returns `404`, identical to a nonexistent id**
(never `403`; its existence is not revealed). Only `GET` is allowed; `POST`/`PUT`/`PATCH`/`DELETE` → `405`
(a `POST` here never creates an order). Error body: `{"error": {"code": "error", "message": "No Order matches the given query."}}`.

Reads are side-effect free: they never touch stock, carts, order status or order contents. Everything returned comes
from the stored `Order`/`OrderItem` snapshot, never from the live catalog or the user's current phone, so later
catalog or profile edits do not change what the API returns (tested).

### POST errors (`{"error": {"code", "message"}}`, same envelope as the rest of the API)
| HTTP | code | when |
|---|---|---|
| 400 | `validation_error` | missing/blank/over-length/non-string delivery field or invalid `postal_code` (`details.<field>[].code`: `required`, `blank`, `null`, `max_length`, `not_a_string`, `control_characters`, `invalid_postal_code`); an empty body (every field `required`); valid JSON that is not an object (`details.non_field_errors[].code`: `invalid` for a list, string, number or boolean, `null` for `null`). Messages never contain the submitted value. |
| 400 | `parse_error` | the body is not syntactically valid JSON (no `details`; the message never quotes the body) |
| 400 | `empty_cart` | valid details but no cart row / no lines (this is also what a repeated submit gets) |
| 401 | `not_authenticated` | anonymous |
| 403 | `csrf_failed` | missing/invalid CSRF token |
| 409 | `item_unavailable` | any line's variant size / color / product / category is gone, inactive or unpublished |
| 409 | `insufficient_stock` | any line's quantity exceeds current stock (stock `0` included) |

Delivery details are validated **first**, before the transaction starts, so invalid details take no lock and create
no order, change no stock and leave the cart as it was. As a consequence an invalid body on an empty cart answers
`validation_error`, not `empty_cart`.

A 409 rejects the **whole** order: no order, no stock change, the cart is left exactly as it was. If both problems
exist, `item_unavailable` wins. The response does not say which line failed; `GET /api/cart/` already reports a
per-line `availability` the client can show.

## What happens (one atomic transaction, `services.create_order(user, delivery)`)
0. (Before the transaction, in the view) validate the delivery details; `create_order` also requires all five
   `Order.DELIVERY_FIELDS` keys and copies exactly those, so no other value can reach the order.
1. Lock the caller's `Cart` row (`SELECT … FOR UPDATE`). A concurrent double submit waits, then finds the cart
   empty and gets `400 empty_cart`, so it can never create two orders.
2. Lock every purchased `VariantSize` row (`FOR UPDATE OF` that table only), **always in primary-key order**, so
   concurrent checkouts over the same items cannot deadlock.
3. Revalidate from the locked rows: still purchasable (same rule as the cart, `purchasable_variant_sizes()`) and
   enough stock.
4. Price every line from the live catalog (`Product.current_price`: `sale_price` if set, else `price`); the cart
   stores no prices. `subtotal = unit_price × quantity`, `total = Σ subtotal`. No shipping, tax or currency.
5. Decrement stock with a guarded update (`stock_quantity >= quantity`), a second line of defence on top of the
   row lock; stock can never go negative (also a DB constraint on the column).
6. Insert `Order` (status `pending`, `payment_status` `unpaid`, delivery snapshot, `customer_phone` = the user's phone at
   that moment) and its `OrderItem`s,
   then delete the cart's lines (the empty `Cart` row stays).
Any exception anywhere rolls all of it back (tested by failing after the stock decrement and order insert).

## Duplicate submission and lost responses
- **Server:** there is no idempotency key. A double or concurrent submit is safe (the cart lock makes the second request
  find an empty cart and get `400 empty_cart`), but a client that never received the response to `POST /api/orders/`
  cannot tell from that call alone whether the order exists, and `empty_cart` on a retry is ambiguous: the lost attempt
  may have created the order, or the cart was emptied elsewhere. The existing read endpoint `GET /api/orders/` is the only
  way to find out. No endpoint, field or status was added for this.
- **Frontend recovery** (`CheckoutForm.tsx`, matching in `lib/checkout/model.ts`): after an unconfirmed outcome (network
  failure or timeout, 5xx, a 2xx whose body is not a valid order) that leaves the cart empty, or after `400 empty_cart`
  on a submit, the page reads `GET /api/orders/`. An order is shown as this submission's result only if **all** hold: its
  id is higher than every order the customer had when the form was shown (read in the background, only for a signed-in
  customer with a non-empty cart); its five delivery fields equal what was sent (the postal code after the same digit
  normalization the server applies); and its lines (variant size id and quantity) equal the cart lines that were submitted.
  Prices, totals and statuses are not compared; the page then shows the order exactly as Django returned it (`pending`,
  `unpaid`). If the cart is still non-empty after an unconfirmed outcome, the form stays with the "couldn't confirm"
  banner and a retry is possible. In every other case (baseline not read yet, orders unreadable, no match, cart changed in
  another tab) the page shows "Please check before ordering again" (`role="alert"`, no form) and never claims success or
  that the order was not placed.
- **Limits:** matching is a heuristic, not an identifier. An identical order (same address and lines) placed from another
  tab or device after the form was shown is indistinguishable and would be shown; it is a real order and none is created
  twice. A submit that happens before the background read finishes, or a request still running on the server when the
  20 s client timeout fires, falls back to the uncertain state. The list is read unpaginated. A server-side idempotency key
  would remove the guesswork but changes the API contract and needs the owner's decision.
- **Price changes:** the order is priced from the live catalog at creation and the contract has no expected-total field,
  so a customer is not warned if a price changed after they saw the cart; the confirmation shows the real total.

## Data decisions
- **Snapshots:** `OrderItem` stores `product_name`, `color_name`, `size_label`, `sku`, `unit_price`, `quantity`,
  `subtotal`; `Order` stores `customer_phone`. Later catalog/user edits do not change history (tested).
- **References are `PROTECT`:** `Order.user` and `OrderItem.variant_size`. A purchased variant size (or the user)
  cannot be deleted while orders reference it; deactivate (`is_active=False`) instead. Deleting such a product
  through the admin is blocked by Django's protected-objects page for the same reason.
- **Stock timing:** decremented at order creation (as `CART.md`/`CATALOG.md` prescribe). Because nothing can cancel,
  expire or restock an order yet, stock removed here is not returned automatically.
- **Cart limits** (`CART_MAX_ITEM_QUANTITY`, `CART_MAX_LINES`) are enforced by the cart, not re-checked here.

## Delivery details (Agent 11, Session 1)
- **Delivery phone = account phone.** The order stores no separate recipient phone. `customer_phone` is
  `user.phone` at order time (canonical `+989XXXXXXXXX`, produced by `apps/accounts/phone.py`) and doubles as the
  delivery contact. A client-supplied phone cannot differ from it because none is accepted (tested).
  Limitation: the account phone is verified by OTP when the account is created and customers cannot change it through
  the API, but **staff can edit it in Django admin without re-verification**; orders keep their own snapshot, so a
  later edit never changes a placed order.
- **Snapshot:** the five delivery fields are flat columns on `Order` (no address book, no second source of truth).
- **Migration `0002`:** hand-written (no Django in the authoring environment; CI's `makemigrations --check` is the
  consistency check). Adds six NOT NULL columns with constant defaults (`''` and `'unpaid'`), a metadata-only change
  on PostgreSQL 11+. **Orders created before this migration keep blank delivery fields** and `payment_status`
  `unpaid`; they stay readable (tested against PostgreSQL by migrating back to `0001`, inserting, migrating forward).
  No non-blank DB constraint exists, because it would fail on those rows; "required" is enforced by the API.
- **Payment:** `payment_status` is server-owned, read-only, and has the single value `unpaid`. Nothing sets another
  value; real payment is not integrated (see `PAYMENT.md`). The browser cannot influence it.
- **Duplicate submission:** there is no idempotency key. The cart row lock makes a repeated or concurrent submit
  safe (the second one gets `400 empty_cart`), but a client that lost the response cannot tell whether the order was
  created; it should check `GET /api/orders/` before retrying.
- **Inventory risk (unchanged behavior, documented):** stock is decremented when the order is created. If an order is
  created but payment is never completed, the order may continue to reserve/decrement inventory indefinitely, because
  order expiry, cancellation and stock restoration are not implemented. The owner must decide that policy before
  online payment goes live; staff can only correct stock manually through the inventory adjustments.

## Not implemented (by design, so far)
Guest checkout; status transitions, cancellation, refunds and restocking; any payment processing (only the `unpaid`
boundary exists); shipping cost/rules, tax, currency; a public order number; idempotency keys; pagination of the order list; customer order list/detail pages in the frontend (sign-in, add-to-cart, cart and
checkout pages exist). Staff can inspect orders in a read-only Django admin (`apps/orders/admin.py`, see `ADMIN.md`).

## Tests
`tests/test_orders_api.py`: auth/CSRF/405, success + snapshot + server totals + sale price, price read at checkout,
ignored client fields and other users' carts untouched, empty/missing cart, repeat submit, insufficient/out-of-stock
and four unavailability causes (whole order rejected, nothing changed), catalog edits don't alter orders, PROTECT,
rollback after failure at two different points, and real-thread concurrency (last unit not oversold, double submit,
opposite-order carts without deadlock).

`tests/test_orders_read_api.py` (reads): anonymous 401 on list/detail, list contains only the caller's orders
(other user's data absent), empty list, client-supplied user ids ignored, own detail 200, foreign order 404 (not 403)
and byte-identical to a nonexistent id, newest-first ordering with id tiebreaker, item/money snapshot values,
list == detail representation, catalog and phone edits don't change responses, `no-store, private` on every
response (200/404/401), GETs mutate nothing (orders, items, cart, stock), constant query count as orders grow, and
405 for unsupported methods (incl. `POST` on the detail not creating an order).

`tests/test_orders_checkout_details.py` (Agent 11): required/blank/null/over-length/non-string/control-character
delivery fields and invalid postal codes each leave orders, stock and cart unchanged; Persian digits and trimming;
exact maximum lengths; leading/trailing/embedded control characters rejected with that single field as the only error; no echo of submitted values and no logging of them; invalid JSON syntax (`parse_error`), empty and non-object bodies (`validation_error`); a self-test that the shared "nothing changed" snapshot (orders, order items, cart lines with variant and quantity, all stock) detects each kind of change; validation-before-cart
ordering; account phone cannot be overridden and its snapshot survives a later account-phone change; client cannot set
`payment_status`/`status`/`total`/owner/id; service ignores non-delivery keys and requires all five fields; valid body
does not bypass 401/CSRF; another customer gets 404 and no address; legacy order without delivery data is readable.
`tests/test_orders_postal_code.py`: the pure normalizer. `tests/test_orders_migration.py`: migration with an existing
order on real PostgreSQL. The existing order/inventory tests only gained the shared `DELIVERY` payload
(`tests/conftest.py`); no assertion about stock, locking or concurrency was changed.

Frontend recovery (no backend change): `e2e/tests/checkout-recovery.spec.ts` (16 pure unit tests of the matching rules) and
two browser tests in `e2e/tests/checkout.spec.ts` that make the response disappear AFTER Django created the order
(`route.fetch()` then `abort()`): one recovers and shows the real order with no second order, the other also fails the
order lookup and must stay uncertain.
