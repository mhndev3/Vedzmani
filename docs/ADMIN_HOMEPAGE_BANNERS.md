# Homepage banner management

The Persian admin workspace manages homepage hero banners at `/[locale]/admin-panel/homepage/banners`.

## Admin API

- `GET /api/admin/homepage/banners/`: list banners.
- `POST /api/admin/homepage/banners/`: create a banner using multipart form data.
- `GET /api/admin/homepage/banners/{id}/`: retrieve one banner.
- `PATCH /api/admin/homepage/banners/{id}/`: update metadata, replace either image, or change publication status.

The API requires an active staff account and the corresponding Django model permission (`view_homepagebanner`, `add_homepagebanner`, or `change_homepagebanner`). Session authentication and CSRF remain in force. There is no physical-delete route; set status to `draft` to stop displaying a banner.

## Image and link rules

- Desktop image is required; mobile image is optional.
- JPEG, PNG, and WebP images are accepted, up to 8 MiB and 40 megapixels per image; combined files in one request are capped at 7 MiB to stay below the current reverse-proxy request limit.
- Image files are stored under a server-generated UUID path in the existing media storage.
- Alt text is required for publishing.
- CTA destinations must be same-site relative paths; external URLs and protocol-relative URLs are rejected.

## Publication and storefront

- Status is `draft` or `published`.
- Optional start/end timestamps define the visible window; end must be after start.
- Public endpoint `GET /api/catalog/homepage-banners/` exposes only published banners inside their schedule.
- The homepage displays the published banners in configured order, using the mobile image at narrow viewport widths.
- If no published banner is available or the endpoint fails, the existing static Vedzmani hero remains as fallback.

No inventory, order, checkout, payment, SEP, Enamad, footer, or search behavior is changed.
