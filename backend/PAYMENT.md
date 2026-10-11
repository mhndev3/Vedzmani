# Payment boundary (Agent 11, Session 1)

**Real payment processing is NOT available.** No payment provider has been chosen, configured or integrated, and
nothing in this repository can charge a card, confirm a payment, or mark an order as paid. This document describes
the boundary a future integration must plug into. It is a design note, not an implementation.

## What exists today
- `Order.payment_status` (`apps/orders/models.py`): server-owned, read-only in the API, single value **`unpaid`**.
  Every order starts `unpaid` (including orders created before the column existed) and nothing changes it.
- The order API never accepts `payment_status` (or `status`, `total`, owner...) from the client; a submitted value is
  ignored (tested in `tests/test_orders_checkout_details.py`).
- `Order.total` is the sum of the line subtotals. It **excludes shipping** (no shipping policy exists) and has no
  currency or tax. It is the amount a future payment would be initiated with only once the owner defines those rules.
- Order creation and payment are separate: creating an order does not imply payment, and the UI must never describe a
  just-created order as paid.

## Decisions still needed from the owner (not invented here)
Payment provider/gateway and its fee and settlement model; whether V1 takes online payment at all or confirms payment
manually; currency and display unit; shipping cost rules (they change the payable amount); the order state machine;
and the policy for unpaid orders (below).

## Unresolved inventory risk
Stock is decremented when the order is **created** (unchanged from Agent 9/10). If an order is created but payment is
never completed, the order may continue to reserve/decrement inventory indefinitely, because order expiry,
cancellation and stock restoration are not implemented. The owner must decide the policy (for example a payment
window, expiry, cancel + restock) before online payment goes live. Do not add payment without it.

## Minimum requirements for a future integration
1. **Provider-neutral adapter, selected by environment settings** (same pattern as `OTP_DELIVERY_BACKEND` in
   `apps/accounts/delivery.py`): a small interface (`initiate(order) -> redirect/session`, `verify(reference) ->
   result`), a setting naming the implementation, and a default that refuses to run when unconfigured (never a fake
   success). Credentials come from environment variables, are never committed, never logged, and never reach the browser.
2. **Server-side initiation from the stored order.** The amount is read from `Order.total` on the server, for an order
   owned by the authenticated user and still `unpaid`. The client sends at most an order id; never an amount or a status.
3. **Verified confirmation only.** An order may leave `unpaid` only through a signature-verified provider callback or
   webhook, preferably followed by a server-to-server verification call to the provider, with the verified amount and
   currency compared to the stored order. The browser return/redirect page is **never** proof of payment: it may only
   show "we are confirming your payment" and read the order status from the API.
4. **Idempotent processing.** Store the provider's transaction reference with a unique constraint; a replayed or
   concurrent callback must be a no-op. Callbacks are CSRF-exempt by necessity, so authenticity must come from the
   signature check, not from cookies.
5. **Transaction-safe transitions.** Change `payment_status` inside one transaction that locks the `Order` row
   (`select_for_update`), re-checks the current state, validates the transition and records the provider reference.
   Lock ordering must stay compatible with order creation (cart row, then `VariantSize` rows in primary-key order).
6. **New states by migration.** `unpaid` is the only value today. Values such as `paid` or `failed` and their allowed
   transitions are added together with the provider decision, with tests that prove no code path reaches `paid`
   without verified confirmation.
7. **No sensitive payment data in our database or logs.** No card numbers, CVVs or raw credentials in orders, users or
   logs. Hosted provider pages are preferred so card data never touches this system.
8. **Frontend:** display only what the API returns (`payment_status`); no payment state, price or total is decided in
   browser state; no provider secrets in `NEXT_PUBLIC_*` variables.

## Tests a future integration must add
Forged or unsigned callback rejected; replayed callback idempotent; amount mismatch rejected; callback for another
user's or an unknown order rejected; concurrent callbacks and a concurrent order change leave one consistent state; the
return page without a verified callback leaves the order `unpaid`.
