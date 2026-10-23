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
| Users | Phone-based add/change forms (phone is normalized with `apps/accounts/phone.py`, duplicates in any spelling are form errors). Search accepts any phone spelling. The password hash is never rendered, only "set / not set" plus a change-password link. Only superusers manage staff accounts: non-superusers cannot change `is_staff`, `is_superuser`, groups or permissions, and cannot edit, delete or reset the password of any staff or superuser account (customer accounts stay manageable). See "Access policy" below. |
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

## Access policy and sensitive operations (Agent 7, Sessions 1-2)
Everything below is enforced on the server (`has_*_permission`, read-only fields, `get_search_fields`); hiding a button
is never the control. Each protection has a regression test (`tests/test_admin_security.py`,
`tests/test_admin_operations.py`) and was checked by removing it and watching the test fail.

**Who may open `/admin/`:** an active user with `is_staff`, then only the pages their model permissions allow. Nobody
receives permissions automatically. Anonymous users and customers (`is_staff=False`) are redirected to the login page;
staff without a permission get 403.

**Superuser-only (policy confirmed by the project owner):**
| Operation | Rule |
|---|---|
| Change `is_staff`, `is_superuser`, a user's groups or user permissions | read-only for non-superusers (the field is ignored if posted) |
| Edit, delete or reset the password of a staff or superuser account | refused (403) for non-superusers, including bulk delete |
| Add, change or delete groups | superusers only; others holding `auth.*_group` can read groups but not change them |

Why: two escalation paths were reproduced before this change. (1) A staff user with only `auth.change_group` could add
`orders.view_order_pii` to a group they belong to. (2) A staff user with only `accounts.change_user` could reset another
staff member's password and sign in as them, or give a customer a password plus `is_staff` and sign in to the admin as
that customer; the admin and the storefront API share one Django session, so that session would also be valid for the
customer API. Non-superusers can still deactivate or reactivate customers, create customer accounts, and change their
own password at `/admin/password_change/`. Keep the number of superusers small.

**Phone numbers.** Full phone numbers are visible to holders of `accounts.view_user` / `accounts.change_user` (user admin)
and `orders.view_order_pii` (orders). The cart admin masks the owner and now searches by phone only for staff holding
`accounts.view_user` or `accounts.change_user`; before, anyone with cart access could recover the hidden digits by
searching substrings. The order list shows the account id, so grant `accounts.view_user` only to people who may see phone
numbers. Query-string lookups on the cart changelist were already refused (400).

**Stock.** `VariantSize.stock_quantity` is read-only everywhere; change it only through Inventory adjustments
(`inventory.add_inventoryadjustment`, `services.adjust_stock`, append-only history). The variant-size list has a
"stock" filter (Out of stock = 0, In stock > 0). There is no low-stock threshold: none has been decided.

**What staff must not do manually:** edit stock any other way; delete products, variants or sizes that have orders or
adjustments (deactivate them instead, deletes are blocked by `PROTECT`); share an account.

## Known gaps (not fixed here)
- **No order-status or payment workflow.** `Order.status` only has `pending` and `payment_status` only has `unpaid`; no
  transitions exist, and the project owner has not decided the state machine, cancellation or restock policy. Orders are
  therefore read-only in the admin and no status action is offered. Follow-up once decided: a service (like
  `adjust_stock`: one transaction, row lock, allowed-transition check, audit row) and an admin action that only calls it.
- **Admin login throttling exists only in Nginx.** Django has no lockout: on 2026-10-24 a correct password was still
  accepted after 30 failed attempts sent straight to Django. Since `main` `074b43c` Nginx limits `POST /admin/login/`
  (10 requests/minute per address, burst 5). Verified here against the repository's `nginx/default.conf` with stub
  upstreams: 12 POSTs gave 6 x 200 then 6 x 429, and loading the login page was never limited. The key is the address
  Nginx sees, so behind a CDN/WAF it is the edge address until real client IPs are restored, and any path that bypasses
  Nginx is unprotected. There is no per-account lockout.
- **Staff login needs the canonical phone** (`+989XXXXXXXXX`); `0912...` is rejected. Left to the authentication owner.
- Viewing PII is not audit-logged.

## Static files (verified 2026-10-24, Windows host, Python 3.14.6, Django 5.2.18)
Status: **admin assets are not served in the current deployment topology.**
- Verified by running: under `config.settings.prod` (throwaway environment, no database contact) `GET /static/admin/css/base.css`
  returns **404**, `/admin/login/` returns 200 and references that stylesheet, and no WhiteNoise middleware is installed.
- Verified by running: `collectstatic` under `config.settings.prod` into a temporary directory produced 154 files
  (including `admin/css/base.css`, `admin/js/theme.js` and `rest_framework/`); `tests/test_admin_operations.py` also checks
  that every `/static/` URL requested by the main admin pages is produced by `collectstatic`.
- Verified by running (re-run on `main` `074b43c`, after the login-throttle change): the repository's `nginx/default.conf` (syntax OK) in front of two stub upstreams sends `/admin/` and
  `/api/` to the backend and **`/static/...` to the frontend**. Limits: stubs, not the real Next.js app, and the image was
  `nginx:alpine`, not the `1.27-alpine` pinned in Compose.
- Not verified: a full Compose stack, a browser, any real deployment.
- Requirement (an infrastructure/owner decision, not changed here): serve `STATIC_URL=/static/` from `STATIC_ROOT`
  (`backend/staticfiles`, gitignored) and run `collectstatic` as a deploy step (no database needed). Options (WhiteNoise,
  shared volume plus an Nginx `location /static/`, or CDN) are compared in the production deployment draft on branch
  `agent/17-production-readiness-session-01` (not merged when this was written). The Dockerfile currently has no
  `collectstatic` step and Compose runs `config.settings.dev`.

## Verification record (Agent 7, Session 2, 2026-10-24)
Python 3.14.6, Django 5.2.18, pytest 8.4.2, disposable PostgreSQL 16 container. `manage.py check` and
`makemigrations --check --dry-run` clean; full `pytest tests` on `main` `074b43c` plus this change: 633 passed (605 before, 3 added upstream, 25 new here). Not verified:
a browser pass through `/admin/`, behaviour behind a real proxy.
