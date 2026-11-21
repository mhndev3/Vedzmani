# Storefront Theme Studio

The Persian admin workspace exposes `/[locale]/admin-panel/storefront/theme`.

## Supported design tokens

- Primary and primary-foreground colors
- Accent and accent-foreground colors
- Approved font presets: system, Persian modern, classic
- Approved corner-radius presets: compact, medium, rounded
- Motion presets: none, subtle, standard

Color values are validated server-side as six-digit HEX values. Font, radius, and motion values use strict allowlists; arbitrary CSS, URLs, font imports, and client-provided CSS are never accepted.

## Workflow

- `GET /api/admin/storefront/theme/`: requires staff plus `catalog.view_storefronttheme`; returns draft and published settings.
- `PATCH /api/admin/storefront/theme/`: requires staff plus `catalog.change_storefronttheme`; validates and saves a draft only.
- `POST /api/admin/storefront/theme/` with `{"action":"publish"}`: publishes the saved draft.
- `GET /api/catalog/storefront/theme/`: public read-only endpoint; returns published settings only, or safe compiled defaults before the first publish.

The editor provides local preview. Publishing is explicit and updates the storefront design tokens at the document root. If the public configuration endpoint is unavailable, the frontend retains the compiled default appearance.

## Security and scope

- Backend staff and Django model permissions are authoritative.
- Mutations use the existing session/CSRF API transport.
- Only allowlisted design tokens are persisted; no arbitrary HTML or CSS is rendered.
- No storefront content, product, stock, order, checkout, SEP, footer, Enamad, or navigation behavior is modified.
- The migration creates one singleton-capable settings row on first admin access; no existing catalog records are changed.
