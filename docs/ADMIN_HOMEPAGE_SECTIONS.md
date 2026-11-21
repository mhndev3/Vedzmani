# Homepage section management API

This phase adds persistent homepage section configuration without changing public storefront rendering.

- Section types: category grid, explicitly selected products, newest products.
- Draft/published status, display order, title/eyebrow, item limit, optional view-all link.
- Category and product selections are relational, not arbitrary JSON.
- Only active categories and active products from active categories can be selected.
- Category sections require categories and cannot include products; product sections require products and cannot include categories; newest-product sections do not accept manual selections.
- Item limit is constrained to 1–24.

## Staff API
Mounted at `/api/admin/homepage/sections/`.
- GET requires `catalog.view_homepagesection`.
- POST requires `catalog.add_homepagesection`.
- PATCH/PUT requires `catalog.change_homepagesection`.
- DELETE requires `catalog.delete_homepagesection`.
- Every operation requires an authenticated active staff account and Django session/CSRF protections.
- No public endpoint is added in this phase. Published sections are stored but do not affect the live homepage until storefront integration.

No arbitrary HTML/CSS/JavaScript, external media URL, stock, order, checkout or payment fields are accepted.
