# Django Admin (Agent 8, Session 1)

Served at `/admin/` by Django's built-in admin. Access = Django session auth + `is_staff` + the stock per-model
permissions (view/add/change/delete). There is no custom RBAC and no custom frontend admin. This is an operations
tool for V1, not a claim of production readiness (static-file serving for admin is still open, see README).

## Logging in
Staff sign in with **phone + password** at `/admin/login/`. The login form does **not** normalize the phone yet:
type the canonical form `+989XXXXXXXXX`. Customers are OTP-only (unusable password) and can never enter the admin
unless explicitly given `is_staff` and a password.

## What exists
| Area | Notes |
|---|---|
| Users | Phone-based add/change forms (phone is normalized with `apps/accounts/phone.py`, duplicates in any spelling are form errors). Search accepts any phone spelling. The password hash is never rendered, only "set / not set" plus a change-password link. Non-superusers cannot edit `is_superuser`, groups or permissions, and cannot edit/delete/reset superusers. |
| Catalog | Category / Collection (activate + reorder in the list), Size, Product (publication toggle in the list, price + read-only `current_price`, collections, color variants inline, search by SKU), ColorVariant (**sizes/stock and images are edited here**, Django has no nested inlines), VariantSize, VariantImage. |
| Cart | `Cart` / `CartItem` are **view-only** (no add/change), owners are masked in lists (`+9891****789`). Delete permission is intentionally left to Django: overriding it would block deleting a user who has a cart. |
| Not registered | `OTPChallenge` (authentication state: code hash + salt). |

## Caveats
- `VariantSize.stock_quantity` is editable in admin because no inventory module exists yet. After orders exist,
  an admin edit can overwrite a concurrent decrement; stock changes must then go through the inventory module.
- Image rules (one primary per variant, unique position) are DB constraints. The admin turns violations into form
  errors, and moving the primary flag between images works in a single save.
- Tests: `tests/test_admin_*.py` (access control, user forms, validation, N+1 guard on every changelist).
