# Vedzmani Admin Workspace: Scope and Delivery Plan

Status: implementation started on `feat/admin-workspace-foundation`.

## Product principles

- Persian-first interface, RTL, plain language, responsive layouts, and workflows that a newly hired operator can learn quickly.
- Storefront-first editing: staff browse the real storefront and open contextual edit tools only when authorized.
- One source of truth: every mutation is validated and persisted by Django APIs; the storefront, search, filters, category pages, and homepage read the same published records.
- Permission checks are enforced by the backend for every read and write. Hiding controls in the frontend is not authorization.
- Preview before publish, explicit save/publish states, clear validation errors, and an audit trail for consequential changes.
- Preserve current catalog, inventory, authentication, privacy, and order invariants. Do not activate checkout, orders, or SEP payments as part of admin work.

## Reference review

The scope is informed by the documented administration capabilities of major commerce platforms:

- Shopify groups operations around orders, products, customers, analytics/reports, marketing/promotions, discounts, content, files, online-store design, settings, and finance. It also provides global admin search and role-based staff permissions. See [Shopify admin navigation](https://help.shopify.com/en/manual/shopify-admin/shopify-admin-overview) and [store permissions](https://help.shopify.com/en/manual/your-account/users/roles/permissions/store-permissions).
- BigCommerce highlights a customizable dashboard, store performance, order and product search, notifications, product/catalog management, customers, storefront content/design, analytics, inventory, and order management. See [Control Panel overview](https://support.bigcommerce.com/s/article/Getting-Started-with-the-New-Control-Panel?language=en_US) and [platform capabilities](https://www.bigcommerce.com/product/).
- WooCommerce organizes its admin around store operations, products, analytics, marketing, customers, orders, coupons, shipping, payments, account/privacy, email, integrations, and system status. Its Shop Manager role illustrates separating operational access from unrestricted administrator access. See [menu structure](https://woocommerce.com/document/woocommerce-menu-items/), [roles and capabilities](https://woocommerce.com/document/roles-capabilities/), and [settings](https://woocommerce.com/document/configuring-woocommerce-settings/).

These are reference patterns, not a mandate to copy every feature or introduce unrelated infrastructure.

## Complete capability inventory

### 1. Identity, security, and staff operations
- Reuse the existing phone-based identity and Django session; never create a parallel customer database or a weaker admin-only auth bypass.
- Staff sign-in must satisfy the existing staff-password security gate. Any unified sign-in work must preserve protection against OTP-only staff sessions opening admin routes.
- Staff directory, active/inactive status, role/group assignment, granular permissions, least-privilege role templates, session revocation, and sensitive-action re-authentication.
- Backend permission checks on every endpoint, CSRF protection, rate limiting, and safe handling of personal data.
- Audit events: actor, action, entity, timestamp, before/after summary, request correlation; never log passwords, OTPs, session secrets, or full payment credentials.

### 2. Dashboard and navigation
- Persian RTL dashboard with configurable cards, recent activity, actionable warnings, setup checklist, and shortcuts.
- Global search across products, variants/SKUs, categories, customers, and orders, with permission-aware results.
- Notifications for low stock, out-of-stock items, failed media processing, pending content, and system/configuration warnings.
- Responsive navigation, breadcrumbs, recent pages, and help text.

### 3. Product and catalog management
- Create, preview, publish, unpublish, duplicate, archive, and (only when safe) delete products.
- Select existing category or create one in context; changes must immediately flow into category navigation, homepage modules, filters, and search.
- Product title, description, slug, metadata, status, price in toman, optional compare-at price/discount fields, and merchandising labels.
- Multiple color variants per product; color name and color palette/hex selection; stable unique variant code.
- Multiple sizes per color, selecting existing sizes or creating new size options.
- Measurement templates with existing measurement names as defaults, editable values per size, and ability to define additional measurement labels.
- Stock displayed per color-size combination and aggregate totals. All stock mutations must use the existing locked, audited inventory-adjustment service; never write stock directly from a product form.
- Multiple images per color variant; upload, preview, reorder by drag-and-drop, set primary image, alt text, replace, and remove. First image is primary and ordering is deterministic.
- Product code generation must be atomic and collision-safe under concurrent creation; never calculate the next code only in the browser.
- Bulk actions, filters, sorting, pagination, CSV import/export with validation and error report, and change history.
- Preserve existing price, variant, measurement, image uniqueness, and inventory constraints.

### 4. Categories, collections, and navigation
- Create/edit/archive categories; name, slug, description, image, parent, visibility, SEO fields, and ordering.
- Collections/curated groups with manual product selection and/or supported rules.
- Preview category cards and category pages.
- One canonical category source feeds storefront navigation, homepage, search, and filters.

### 5. Inventory and purchasing operations
- Variant-size stock ledger, adjustment reasons, operator, timestamps, and immutable history.
- Low-stock thresholds, out-of-stock views, stocktake/count adjustment, discrepancy reporting, and CSV export.
- Inventory overview and (future) supplier/purchase-order records only if the business process is approved.
- No direct stock overwrite; no stock decrement on unpaid/unapproved orders.

### 6. Storefront visual editor and content management
- Contextual pencil/edit controls visible only to authorized staff on storefront pages.
- Edit the current page/section in place with draft preview, save, publish, rollback, and clear unsaved-change warnings.
- Homepage hero banners, image and mobile image, CTA label/link, schedule, visibility, ordering, and accessibility text.
- Homepage section builder: title, section type, selected categories/products/collection, sort rule, visibility, and ordering.
- Dynamic text for page headings, product/category descriptions, navigation labels, FAQ, about, support, footer, empty states, and CTA copy.
- Media library with upload, search, dimensions, alt text, usage references, and safe deletion checks.
- Theme presets, colors, typography, spacing, borders, button styles, animation presets, reduced-motion support, and preview before publish.
- Draft/published versions, revision history, rollback, and cache invalidation after publication.

### 7. Promotions and merchandising
- Discount campaigns, scheduled sale prices, coupon codes, usage limits, date windows, eligible products/categories, and stacking rules.
- Curated shelves such as newest, offers, best sellers, featured, seasonal, and manually selected products.
- Promotional badges and landing pages, with clear rules and preview.
- Do not imply a discount or sale price unless the backend pricing rules actually apply it.

### 8. Orders, delivery, returns, and support
- Orders list/detail with status, timeline, customer and line-item snapshots, internal notes, and safe export.
- Preserve current read-only order policy until a separately approved order-operation design exists.
- PII shown only with explicit permission and audited access.
- Shipping methods, delivery zones, pricing rules, tracking references, and carrier integration only after Post/Tipax requirements are confirmed.
- Return/exchange requests, reason codes, review workflow, and support tickets/notes.
- Payment and refund operations remain disabled until SEP onboarding, callback verification, reconciliation, and inventory reservation/refund rules are approved and tested.

### 9. Customers and customer care
- Searchable customer directory with privacy-aware profile and order history.
- Account status, support notes, consent/preferences, and customer communication history.
- Export and bulk operations gated by explicit permissions; avoid exposing national IDs or addresses without a business need.

### 10. Analytics and reporting
- Dashboard for traffic, product views, search terms, conversion funnel, inventory, category performance, and sales once orders are enabled.
- Date ranges, comparisons, CSV exports, and definitions for every metric.
- Never fabricate revenue or conversion values while checkout/orders are disabled.

### 11. Store configuration and operations
- Store identity/contact details, social links, footer, locale, currency display, and SEO defaults.
- Shipping/payment configuration surfaces may be visible as disabled/setup-required until approved.
- Health/status view for app dependencies, recent deploy/release, failed jobs, and backup freshness; no destructive controls in the admin UI.
- Import/export, data retention, privacy requests, and operational runbooks.

### 12. Workflow and automation
- Explicit draft/review/publish workflow for content.
- Safe reusable rules for low-stock alerts, scheduled banners, and campaign activation.
- Workflow run history, actor, outcome, retry policy, and failure notifications.
- No autonomous order/payment/inventory automation until its business rules and safeguards are separately approved.

## Delivery phases

1. **Foundation (current branch):** staff-aware storefront menu entry, Persian admin workspace shell, permission-aware landing page, and documented scope. Keep the existing admin security gate intact.
2. **Admin API and authorization:** explicit admin permission layer and tests; avoid using `is_staff` alone for every future capability.
3. **Catalog workflow:** full product create/edit/archive flow, variants, sizes, measurements, media upload/reorder, atomic product codes, and audited stock adjustments.
4. **Categories and collections:** canonical dynamic taxonomy and homepage collection primitives, wired into search/filter/navigation.
5. **Storefront editor:** contextual pencil controls, drafts, preview, publish, rollback, and revision history.
6. **Homepage/content/theme studio:** banners, text, sections, theme presets, animation settings, media library.
7. **Operations modules:** inventory, customers, support, orders (after explicit approval), delivery, promotions, analytics, staff roles, audit logs.
8. **Hardening:** focused unit/API/component tests, accessibility, mobile usability, permission matrix, backup/restore compatibility, performance, and deployment smoke checks.

## Release gates

- No production deployment from this branch until review and CI are green.
- Do not run broad or unrelated E2E suites for a narrow change unless required by repository CI policy; focus on the affected paths.
- No `docker compose down -v`, no destructive database reset, and no production data mutation for UI testing.
- Orders, checkout, and SEP stay disabled throughout this work unless the owner explicitly approves a separate activation plan.
