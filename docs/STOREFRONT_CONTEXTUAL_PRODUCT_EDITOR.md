# Storefront Contextual Product Editor

This change starts the storefront-first editing phase with a deliberately narrow, permission-checked product content editor.

## What is included

- A staff-only "ویرایش همین محصول" control on both product detail URL shapes.
- Editable product name, description, base price, and optional sale price.
- A local preview of the edited content before saving.
- Client-side validation for required title and whole-Toman positive prices; sale price must be lower than base price.
- Save through the existing `PATCH /api/admin/catalog/products/{id}/` endpoint.
- The backend remains authoritative: staff status and `catalog.change_product` permission are checked by the existing admin API, and CSRF/session behavior is unchanged.
- On success, the product detail route refreshes to show the persisted values.

## Explicit boundaries

- This is an initial contextual editor, not the complete page builder.
- Preview is local to the editor; there is not yet a persisted draft, approval queue, separate publish action, revision history, or rollback.
- The editor does not change product status, slug, category, collections, variants, sizes, images, measurements, or stock.
- No backend, database schema, migration, authentication, inventory, order, checkout, or SEP changes are included.
- Products that are inactive remain inactive; this editor does not publish or activate them.

## Authorization

The frontend checks the current session only to decide whether to show the control. This is not an authorization boundary. The existing Django admin API independently requires an active authenticated staff account and the model-level `catalog.change_product` permission for the PATCH request. A staff account without that permission receives a forbidden response.

## Verification

CI should cover the frontend type/lint/build checks and the repository's configured E2E checks. No production deployment is part of this PR.
