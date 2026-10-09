# Cart API (Agent 7, Session 1)

App: `backend/apps/cart`. PostgreSQL is the source of truth. **The cart is not an inventory reservation.**

```
User ─1:1─ Cart ─< CartItem >─ catalog.VariantSize   (unique (cart, variant_size); quantity > 0 by DB check)
```

## Contract
Base path `/api/cart/`. JSON in/out. **Auth: Django session cookie (same as `AUTH.md`); anonymous → `401 not_authenticated`.**
Every non-GET request needs the CSRF header `X-CSRFToken` (`GET /api/auth/csrf/`), otherwise `403 csrf_failed`.
The owner is always `request.user`; no user/cart id is ever accepted from the client (extra body fields are ignored).
Responses are `Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private`.

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/api/cart/` | – | `200` cart |
| DELETE | `/api/cart/` | – | `200` empty cart (idempotent) |
| POST | `/api/cart/items/` | `{variant_size_id, quantity?=1}` | `201` cart. Existing line for the same `variant_size_id` is **incremented**. |
| PATCH | `/api/cart/items/<item_id>/` | `{quantity}` | `200` cart. Sets the absolute quantity. |
| DELETE | `/api/cart/items/<item_id>/` | – | `200` cart |

`variant_size_id` is `VariantSize.id` — already exposed as `colors[].sizes[].id` by `GET /api/catalog/products/<slug>/`.
`<item_id>` is the cart line `id` from the cart response.

### Cart response (every endpoint returns this shape)
```
{ items: [{ id, quantity, availability, unit_price, subtotal,
            product{id,name,slug}, color{name,slug,hex_color},
            variant_size{id,sku,size,label}, image{url,alt_text,width,height}|null }],
  item_count,        // distinct lines
  total_quantity,    // units on lines that are not "unavailable"
  total,             // sum of subtotals of lines that are not "unavailable"
  has_issues }       // any line is not "available"
```
Money = whole-unit Decimal rendered as a string (same as the catalog; currency still undecided). `unit_price` is
`Product.current_price` (`sale_price` if set, else `price`), read from the catalog on **every** request; nothing is
copied into the cart, so prices can never be stale or client-controlled. `subtotal = unit_price × quantity` (Decimal).
`availability`: `available` | `insufficient_stock` (quantity > current stock) | `unavailable` (variant size, color,
product or category is inactive/unpublished). `unavailable` lines are shown, excluded from totals, cannot be edited
(only removed). Stock numbers are never exposed.

### Errors (`{"error": {"code", "message", "details"?}}`)
| HTTP | code | when |
|---|---|---|
| 400 | `validation_error` | non-integer / `< 1` / `> CART_MAX_ITEM_QUANTITY` quantity (`details.quantity[].code == "max_quantity"` when over the limit, including increments via POST); malformed/missing/out-of-range `variant_size_id`; unknown, inactive or unpublished item (`details.variant_size_id[].code == "unavailable"` — deliberately identical for all three) |
| 401 | `not_authenticated` | anonymous |
| 403 | `csrf_failed` | missing/invalid CSRF token |
| 404 | `not_found` | unknown item id, **or another user's item id** (indistinguishable) |
| 409 | `insufficient_stock` | requested resulting quantity exceeds current `stock_quantity` (incl. stock 0) |
| 409 | `item_unavailable` | PATCH on a line whose product/variant became unpublished |
| 409 | `cart_full` | adding a new distinct line beyond `CART_MAX_LINES` |

## Data integrity decisions
- **Stock:** cart code never writes `stock_quantity` (tested). It is read (unlocked) only to reject impossible
  quantities. A cart item is *not* a promise of purchasability; **checkout must re-validate and decrement under
  `select_for_update` on `VariantSize`**. Stock can drop later → line becomes `insufficient_stock`; the user may
  lower the quantity or remove it.
- **Concurrency:** each mutation is one transaction that locks only the caller's own `Cart` row, serializing that
  user's concurrent requests so quantity/line limits can't be bypassed (regression-tested with real threads; the test
  fails if the lock is removed). `UNIQUE(user)` and `UNIQUE(cart, variant_size)` + `CHECK(quantity > 0)` back this up
  in the DB. Reads take no locks. `VariantSize` rows are deliberately *not* locked (no reservation).
- **Lazy creation:** the `Cart` row is created on first add; `GET`/`DELETE` never create one.
- **Limits** (not specified by product docs → conservative defaults, env-overridable): `CART_MAX_ITEM_QUANTITY=10`,
  `CART_MAX_LINES=50`. Product owner should confirm.
- **Queries:** reading a cart is constant-cost (cart, items joined to size/variant/product/category, active images).
- `CartItem.variant_size` is `CASCADE`: removing a purchasable unit from the catalog drops it from carts. Orders
  (future) must **snapshot** name/SKU/price and use `PROTECT`/no FK to live catalog rows.

## Not implemented (by design)
Guest carts / merge on login, checkout/orders, stock deduction or reservation, coupons, shipping, tax, currency,
cart expiry/cleanup job, frontend wiring (Add to Cart is still a placeholder on the storefront), caching.
