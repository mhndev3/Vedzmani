# Catalog (product domain) — Agent 4, Session 1

App: `backend/apps/catalog`. PostgreSQL is the source of truth.

```
Category ─< Product >─< Collection        (Product.collections, M2M)
              └─< ColorVariant ─┬─< VariantImage   (metadata only, WebP)
                                └─< VariantSize >─ Size   (controlled vocabulary)
```

- `VariantSize` is the **exact purchasable unit** (product + color + size). Cart/order items should FK to it.
  It has a unique `sku` and `stock_quantity` (>= 0).
- **Inventory boundary:** this session only persists the column. Decrement, reservation, checkout validation and
  concurrency control belong to the inventory agent (use `select_for_update` / atomic updates on `VariantSize`).
  Redis must never hold stock.
- Money: `Decimal(14, 0)`; currency/discount rules are undecided (see PROJECT_CONTROL.md). `sale_price`, if set, must be `0 < sale_price < price` (DB check).
- Products are created **unpublished** (`is_active=False`).

## Constraints
- unique: `Category.slug`, `Collection.slug`, `Product.slug`, `Size.code`, `VariantSize.sku`, `VariantImage.storage_key`
- unique: `(ColorVariant.product, slug)`, `(VariantSize.variant, size)`, `(VariantImage.variant, position)`
- partial unique: one `is_primary` image per variant
- checks: positive price, valid sale price, positive image dimensions, `content_type = image/webp`
- FKs: Category/Size are `PROTECT`; Product -> variants -> sizes/images are `CASCADE`
- index: `Product(category, is_active, -created_at)` for the future category listing

## Images
DB stores a **storage key** (relative object path, must end in `.webp`), never a URL or signed URL.
`apps/catalog/storage.py::public_image_url` builds `MEDIA_CDN_BASE_URL + "/" + key`
(env `MEDIA_CDN_BASE_URL`, empty by default). Not implemented: upload to S3, WebP/AVIF conversion, credentials.

## API
`GET /api/catalog/products/<slug>/` — public, read-only; active product/category/variants/images/sizes only;
stock exposed only as `in_stock` boolean; constant query count (tested).

## Not implemented (for later agents)
listing/search/filter/sort API, write APIs, full admin (only bare `admin.site.register`), reviews, favorites,
cart, orders, inventory logic, pricing/discount engine, image upload/conversion, caching.
