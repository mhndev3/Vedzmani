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

### `POST /api/orders/` — create (Session 1)
**No request body** (anything sent is ignored). JSON out. Needs the CSRF header `X-CSRFToken`
(`GET /api/auth/csrf/`), otherwise `403 csrf_failed`.
The order is built from `request.user`'s own cart. No user id, item list, price, status or total is ever accepted
from the client. Responses are `Cache-Control: no-store, private`.

Success `201`:
```
{ id, status: "pending", customer_phone, total, created_at,
  items: [{ id, variant_size_id, product_name, color_name, size_label, sku, unit_price, quantity, subtotal }] }
```
`id` is the database id and the only order identifier (no separate public order number yet). Money is a whole-unit
Decimal rendered as a string, like the catalog and cart (currency still undecided).

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
| 400 | `empty_cart` | no cart row, or the cart has no lines (this is also what a repeated submit gets) |
| 401 | `not_authenticated` | anonymous |
| 403 | `csrf_failed` | missing/invalid CSRF token |
| 409 | `item_unavailable` | any line's variant size / color / product / category is gone, inactive or unpublished |
| 409 | `insufficient_stock` | any line's quantity exceeds current stock (stock `0` included) |

A 409 rejects the **whole** order: no order, no stock change, the cart is left exactly as it was. If both problems
exist, `item_unavailable` wins. The response does not say which line failed; `GET /api/cart/` already reports a
per-line `availability` the client can show.

## What happens (one atomic transaction, `services.create_order`)
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
6. Insert `Order` (status `pending`, `customer_phone` = the user's phone at that moment) and its `OrderItem`s,
   then delete the cart's lines (the empty `Cart` row stays).
Any exception anywhere rolls all of it back (tested by failing after the stock decrement and order insert).

## Data decisions
- **Snapshots:** `OrderItem` stores `product_name`, `color_name`, `size_label`, `sku`, `unit_price`, `quantity`,
  `subtotal`; `Order` stores `customer_phone`. Later catalog/user edits do not change history (tested).
- **References are `PROTECT`:** `Order.user` and `OrderItem.variant_size`. A purchased variant size (or the user)
  cannot be deleted while orders reference it; deactivate (`is_active=False`) instead. Deleting such a product
  through the admin is blocked by Django's protected-objects page for the same reason.
- **Stock timing:** decremented at order creation (as `CART.md`/`CATALOG.md` prescribe). Because nothing can cancel,
  expire or restock an order yet, stock removed here is not returned automatically.
- **Cart limits** (`CART_MAX_ITEM_QUANTITY`, `CART_MAX_LINES`) are enforced by the cart, not re-checked here.

## Not implemented (by design, so far)
Guest checkout; status transitions, cancellation, refunds and restocking; payment; shipping, address/delivery
details, tax, currency; a public order number; idempotency keys; pagination of the order list; admin registration
for orders; frontend wiring (the storefront still has no checkout or order pages).

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
