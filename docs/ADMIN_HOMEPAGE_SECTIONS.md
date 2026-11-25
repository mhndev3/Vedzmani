# Homepage section management API

This workflow adds persistent homepage section configuration and appends published sections after the existing storefront content.

- A free-form staff-defined section label plus a safe content layout: category grid, explicitly selected products, or newest products.
- Draft/published status, display order, title/eyebrow, item limit, optional view-all link.
- Category and product selections are relational, not arbitrary JSON.
- Only active categories and active products from active categories can be selected.
- Category sections require categories and cannot include products; product sections require products and cannot include categories; newest-product sections do not accept manual selections.
- Item limit is constrained to 1–24.
- Published custom sections are appended after the existing category grid and newest-products shelf; they never replace the original homepage content.

## Staff API
Mounted at `/api/admin/homepage/sections/`.
- GET requires `catalog.view_homepagesection`.
- POST requires `catalog.add_homepagesection`.
- PATCH/PUT requires `catalog.change_homepagesection`.
- DELETE requires `catalog.delete_homepagesection`.
- Every operation requires an authenticated active staff account and Django session/CSRF protections.
- No public endpoint is added in this phase. Published sections are stored but do not affect the live homepage until storefront integration.

No arbitrary HTML/CSS/JavaScript, external media URL, stock, order, checkout or payment fields are accepted.
