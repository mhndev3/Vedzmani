# Homepage section management

The custom admin workspace is available at `/[locale]/admin-panel/homepage`.

## Supported sections
- Selected active categories, rendered with a representative active product image when available.
- Selected active products, rendered as existing per-color storefront cards.
- Newest active products, rendered as existing per-color storefront cards.

Each section supports a title, optional eyebrow, display position, item limit (1–24), optional same-site "view all" path, and draft/published status. Reordering swaps adjacent positions. Sections are never physically deleted in this UI; changing a published section back to draft hides it.

## API
- Staff-only management: `/api/admin/homepage/sections/` (existing model permissions, session auth and CSRF).
- Public read-only rendering data: `/api/catalog/homepage-sections/`; returns published sections only, with active categories/products only.

The public API does not expose draft sections. View-all links must be relative same-site paths; external URLs are rejected. The storefront keeps the existing homepage layout when no published sections exist or the new endpoint is unavailable.

## Safety and scope
No stock, order, checkout, payment, SEP, authentication, footer, Enamad, or desktop-search behavior is changed. The existing hero slider remains in place. No new migration is required by this UI/API integration PR.
