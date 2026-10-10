# Orders API (Agent 9, Session 1)

App: `backend/apps/orders`. PostgreSQL is the source of truth. This session only **creates** an order from the
caller's cart. Nothing else about the order lifecycle exists yet (see "Not implemented").

```
User ─< Order ─< OrderItem >─ catalog.VariantSize        (OrderItem unique (order, variant_size); quantity > 0)
```

## Contract
`POST /api/orders/` — **no request body** (anything sent is ignored). JSON out.
**Auth: Django session cookie (same as `AUTH.md`); anonymous → `401 not_authenticated`.** Needs the CSRF header
`X-CSRFToken` (`GET /api/auth/csrf/`), otherwise `403 csrf_failed`. Only `POST` is routed (`405` otherwise).
The order is built from `request.user`'s own cart. No user id, item list, price, status or total is ever accepted
from the client. Responses are `Cache-Control: no-store, private`.

Success `201`:
```
{ id, status: "pending", customer_phone, total, created_at,
  items: [{ id, variant_size_id, product_name, color_name, size_label, sku, unit_price, quantity, subtotal }] }
```
`id` is the database id and the only order identifier (no separate public order number yet). Money is a whole-unit
Decimal rendered as a string, like the catalog and cart (currency still undecided).

### Errors (`{"error": {"code", "message"}}`, same envelope as the rest of the API)
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

## Not implemented (by design, this session)
Guest checkout; order list/detail endpoints; status transitions, cancellation, refunds and restocking; payment;
shipping, address/delivery details, tax, currency; a public order number; idempotency keys; admin registration for
orders; frontend wiring (the storefront still has no checkout).

## Tests
`tests/test_orders_api.py`: auth/CSRF/405, success + snapshot + server totals + sale price, price read at checkout,
ignored client fields and other users' carts untouched, empty/missing cart, repeat submit, insufficient/out-of-stock
and four unavailability causes (whole order rejected, nothing changed), catalog edits don't alter orders, PROTECT,
rollback after failure at two different points, and real-thread concurrency (last unit not oversold, double submit,
opposite-order carts without deadlock).
