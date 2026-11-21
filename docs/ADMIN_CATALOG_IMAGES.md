# Admin catalog image workflow

The staff-only image API is mounted below `/api/admin/catalog/images/`.

- `POST upload/` accepts multipart fields `variant`, `file`, and optional `alt_text`. Source formats are JPEG, PNG, and WebP; each upload is limited to 12 MiB and 40 megapixels. The backend decodes and re-encodes the source as WebP, assigns an opaque server-generated storage key, and lets the existing post-save signal generate responsive renditions.
- `GET ?variant=<id>` lists active images for one color variant in deterministic order.
- `POST reorder/` accepts `{ "variant": <id>, "image_ids": [<id>, ...] }`. The list must contain every active image for that variant exactly once. The first image becomes primary.
- `PATCH <id>/deactivate/` safely hides an image without deleting its binary. If the primary image is deactivated, the next active image is promoted.

Permissions are explicit: upload requires `catalog.add_variantimage` and `catalog.view_colorvariant`; list requires `catalog.view_variantimage`; reorder/deactivate require `catalog.change_variantimage`. All actions also require an active authenticated staff account and the existing Django session/CSRF protection.

Storage keys are never accepted from clients or returned by the API. Original files are retained for cache safety and rollback. Orders and SEP payment configuration are not touched.
