# Customer directory

The custom staff workspace exposes a read-only customer directory at `/fa/admin-panel/customers`.

## Access and privacy
- Requires an active staff account and Django's `accounts.view_user` permission.
- Customer phone is always masked in this workspace.
- Address, national code, full name, email, authentication state and other profile PII are not returned.
- Search accepts account ID only; phone-number lookup is intentionally rejected.
- Staff and superuser accounts are excluded from the customer directory.
- Responses are never cached.
- No create, update, deactivate, delete, export or bulk action is exposed.

## Summary fields
- Account ID, masked phone, active state and join date.
- Order count and sum of recorded order totals, derived from existing order records.
- The total reflects order totals as stored and does not add shipping charges.

Full customer phone and delivery snapshot access remains governed by the separate `orders.view_order_pii` permission in the order workspace. This feature does not change orders, checkout, payment, inventory, OTP, SEP or shipping configuration.
