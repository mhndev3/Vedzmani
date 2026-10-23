# Django Admin (Agent 8, Session 1)

Served at `/admin/` by Django's built-in admin. Access = Django session auth + `is_staff` + the stock per-model
permissions (view/add/change/delete). There is no custom RBAC and no custom frontend admin. This is an operations
tool for V1, not a claim of production readiness (static-file serving for admin is still open, see README).

## Logging in
Staff sign in with **phone + password** at `/admin/login/`. The login form does **not** normalize the phone yet:
type the canonical form `+989XXXXXXXXX`. Customers are OTP-only (unusable password) and can never enter the admin
unless explicitly given `is_staff` and a password.

**A session created by the customer OTP flow never opens the admin** (Agent 6). `apps/accounts/admin_site.py`
refuses sessions flagged by `/api/auth/otp/verify/`, even for `is_staff` phones, so an SMS code alone cannot reach
`/admin/`. Succeeding at `/admin/login/` (password) lifts the restriction for that session; a later OTP login on the
same session closes it again. Staff accounts without a password (shown as "Not set (OTP login only)" in the user
admin) therefore cannot use the admin until a password is set.

## What exists
| Area | Notes |
|---|---|
| Users | Phone-based add/change forms (phone is normalized with `apps/accounts/phone.py`, duplicates in any spelling are form errors). Search accepts any phone spelling. The password hash is never rendered, only "set / not set" plus a change-password link. Non-superusers cannot edit `is_superuser`, groups or permissions, and cannot edit/delete/reset superusers. |
| Catalog | Category / Collection (activate + reorder in the list), Size, Product (publication toggle in the list, price + read-only `current_price`, collections, color variants inline, search by SKU), ColorVariant (**sizes and images are edited here**, stock is read-only; Django has no nested inlines), VariantSize, VariantImage. |
| Cart | `Cart` / `CartItem` are **view-only** (no add/change), owners are masked in lists (`+9891****789`). Delete permission is intentionally left to Django: overriding it would block deleting a user who has a cart. |
| Orders | `Order` / `OrderItem` are **strictly read-only** (no add, change, delete or actions, for superusers too). Full phone and delivery details need `orders.view_order_pii`; see "Orders admin" below. |
| Not registered | `OTPChallenge` (authentication state: code hash + salt). |

## Caveats
- `VariantSize.stock_quantity` is **read-only** in admin (VariantSize page, changelist and the size inline). A new
  size starts at 0 and staff change stock through **Inventory adjustments** (locked, audited, append-only; needs
  `inventory.add_inventoryadjustment`, see `INVENTORY.md`). A direct edit could overwrite a concurrent order decrement.
- Image rules (one primary per variant, unique position) are DB constraints. The admin turns violations into form
  errors, and moving the primary flag between images works in a single save.
- Tests: `tests/test_admin_*.py` (access control, user forms, validation, N+1 guard on every changelist).

## Orders admin (read-only, PII-gated)
Code: `apps/orders/admin.py`, `apps/orders/permissions.py`, `apps/orders/apps.py`. No model fields, no migration, no business logic changed.

**Read-only guarantees** (both `Order` and `OrderItem`, every user including superusers)
- `has_add/change/delete_permission` always return `False`; Django therefore answers `403` to `/add/`, a `POST` to `/<id>/change/` and `/<id>/delete/`. `save_model`, `delete_model`, `delete_queryset`, `save_formset` and `save_related` also raise `PermissionDenied`. `actions` is `None` (no `delete_selected`), nothing is `list_editable`.
- The `change_*` permissions do **not** imply view (Django's default would). Opening the pages needs `orders.view_order` (orders) / `orders.view_orderitem` (items and the items inline).
- The `GET /<id>/change/` page is Django's view-only page: no form, no save buttons, the items inline cannot add, change or delete rows.

**Who sees what**
| | `orders.view_order` (+ `view_orderitem` for items) | additionally `orders.view_order_pii` |
|---|---|---|
| List | id, created, **masked** phone (`+9891****789`), status, payment status, total, item count | same (the list never shows the full phone) |
| Detail | the above + updated time, account id (`#12`, no link), items (SKU, product, color, size, unit price, quantity, subtotal) | + full customer phone, recipient name, province, city, address, postal code |
| Search | order id, item SKU, item product name | + customer phone (any spelling), recipient name |

Without the PII permission, PII is also excluded from: search, the filter sidebar, query-string filters, sorting, the `OrderItem` pages and the popup `_to_field` parameter. Django's default `lookup_allowed` accepts `?customer_phone__startswith=...` and one-relation lookups such as `?order__customer_phone__...` or `?user__phone__...` (a phone-number oracle); both admins use a **whitelist** and answer `400` to anything else, for every user. The masked-phone column is deliberately not sortable.

**The permission `orders.view_order_pii`**
- Created by a `post_migrate` handler (`create_order_pii_permission`), so it exists on new and existing databases after the next `migrate` (even a no-op one) and in the test database. It is not a `Meta.permissions` entry because that would need a migration. The handler is idempotent.
- **Granted to nobody automatically.** An administrator assigns it to a user or, preferably, a group (e.g. "Order PII viewers") in `/admin/` -> Users/Groups. Grant `orders.view_order` and `orders.view_orderitem` alongside it; the PII permission alone opens nothing.
- Django treats an active superuser as holding every permission, so superusers can see PII (they still cannot change anything). Keep the number of superusers small.
- Operational setup after deploying: run `python manage.py migrate` (creates the permission), then create the group and add only the staff who need delivery details.

**Limits**
- Search takes one term (no word splitting). Item search is on the order's snapshot text, not the live catalog.
- Viewing PII is not audit-logged (Django logs only admin changes, and there are none here).
- `/admin/` is still the plain Django admin on the same origin as the storefront API; see the README for the open static-file and network-exposure items.
- Tests: `tests/test_admin_orders.py` (access, PII isolation across list/detail/search/filters/sorting/`_to_field`/items, read-only on every route including superuser and inline POST, bounded query count, permission registration). Verified 2026-10-18 on Python 3.14.5 / Django 5.2.18 / pytest 8.4.2 against a disposable PostgreSQL 16 container: `manage.py check` and `makemigrations --check --dry-run` clean, `tests/test_admin_orders.py` 81 passed, full `pytest tests` 600 passed. Temporarily removing each of the main protections (lookup whitelist, read-only permissions, PII gate, non-sortable phone column, actions disabled, permission registration) made these tests fail. Not verified: a browser pass through `/admin/`, and behaviour under `config.settings.prod`.
