# Cart API

The cart is a non-reserving list of purchasable VariantSize rows. PostgreSQL is authoritative for signed-in carts, prices and inventory state.

## Endpoints

All endpoints use Django session authentication and require X-CSRFToken for unsafe methods. Ownership is derived only from request.user.

| Method | Path | Purpose |
|---|---|---|
| GET | /api/cart/ | Return the authenticated user's cart |
| DELETE | /api/cart/ | Clear the authenticated user's cart |
| POST | /api/cart/items/ | Add a purchasable variant and quantity |
| PATCH | /api/cart/items/<item_id>/ | Set a cart line quantity |
| DELETE | /api/cart/items/<item_id>/ | Remove a cart line |
| POST | /api/cart/merge-guest/ | Atomically transfer a browser guest cart after authentication |

## Guest-cart transfer

Guests can add and edit cart lines in the browser before authentication. The browser stores an opaque variant-size ID, quantity and display snapshots in localStorage. Snapshots (name, color, image and displayed price) are not trusted and are never used by Django to price or authorize a cart line.

When the guest selects «تکمیل خرید», the storefront routes them through the existing phone OTP authentication flow. OTP verification creates a user if the phone number is new. After the session is established, the browser sends a UUID idempotency token and an array of { variant_size_id, quantity } records to POST /api/cart/merge-guest/.

The endpoint is authenticated and CSRF-protected. Django resolves every variant against the active/published catalog, checks current stock and quantity/line limits, merges with the authenticated user's existing cart and builds product, color, image and price fields from the database. The operation is atomic: if any line fails validation, none of the guest items are merged. Client-supplied names, prices, images, cart IDs and user IDs are not accepted.

A UUID token plus server-side payload hash makes a repeated identical transfer idempotent. Reusing a token with a different payload is rejected. This prevents duplicate lines when the browser retries after an uncertain network response.

The guest cart is cleared from local storage only after Django confirms the merge. The signed-in cart remains owned by the current session user.

## Cart invariants

- A cart is not an inventory reservation. Stock is checked when adding, changing quantity and merging, and must be checked again at a future payment/order step.
- Prices are not stored in cart rows. The current product price is read from the catalog on every cart response.
- Each mutation locks only the authenticated user's cart row; ownership is never accepted from request data.
- A cart row is lazily created on first successful addition/merge.
- Default limits are CART_MAX_ITEM_QUANTITY=10 and CART_MAX_LINES=50.

## Final order placement

The checkout screen shows delivery fields and the server-calculated cart summary, but deliberately sends no order request and renders no final «ثبت سفارش» button. Production also keeps ORDERS_ENABLED=False; its API rejects direct attempts to create an order. Enabling order creation requires the payment provider and its verified callback flow.