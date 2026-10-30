# Catalog (product domain) — Agent 4, Session 1

App: `backend/apps/catalog`. PostgreSQL is the source of truth.

```
Category ─< Product >─< Collection        (Product.collections, M2M)
              ├─< ProductSizeMeasurement >─ Size       (per-product, per-size measurement rows)
              └─< ColorVariant ─┬─< VariantImage       (metadata only, WebP)
                                └─< VariantSize >─ Size (color-specific stock by size)
```

- `VariantSize` is the **exact purchasable unit** (product + color + size). Cart/order items FK to it.
  It has a unique `sku` and `stock_quantity` (>= 0); each color owns its own size rows and stock counts.
- `Product.price` / `sale_price` are owned by the product, so every color has the same product price.
- `ProductSizeMeasurement` stores flexible table rows by product + size (name, value, optional unit, position).
  They are shared across that product's colors, and a product may have different rows or no measurements at all
  for any size.
- **Inventory boundary:** (stock adjustments, their audit trail and the read-only admin now live in `apps/inventory`, see `INVENTORY.md`.) This session only persisted the column. Decrement, reservation, checkout validation and
  concurrency control belong to the inventory agent (use `select_for_update` / atomic updates on `VariantSize`).
  Redis must never hold stock.
- Money: `Decimal(14, 0)`; one stored unit is **one Iranian Toman** (never Rial). `sale_price`, if set, must be `0 < sale_price < price` (DB check).
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
In production, binaries live under `MEDIA_ROOT` (default `/app/media`), backed by the host directory
`PRODUCT_MEDIA_DIR` (default `/home/vzinfra/prod/media`). Backend mounts it read/write; Nginx mounts it
read-only and serves `/media/<storage_key>` with immutable caching. The local development Compose
stack uses a persistent `product_media` named volume shared with Nginx read-only. If `MEDIA_CDN_BASE_URL` is set,
`public_image_url` returns the CDN URL instead. Upload/import and WebP conversion are performed by the
separate product-import workflow; the model still stores metadata only.

## API
`GET /api/catalog/products/<slug>/` — public, read-only; active product/category/variants/images/sizes only;
per-size `stock_quantity` and its derived `in_stock` boolean are exposed for the storefront size selector. Each size also includes its product-specific `measurements[]` rows; the same measurement values are returned for the same size in each color, while stock remains color-specific. Constant query count (tested).

### Listing: `GET /api/catalog/products/` (Agent 6, Session 1)
Public, read-only, no auth. Only `Product.is_active` products in an active category are returned. Unknown query
params are ignored; invalid values return `400` with the standard `{"error": {...}}` envelope.

| Param | Meaning |
|---|---|
| `search` | Case-insensitive substring search, DB-side. Whitespace-separated terms (max 5) are ANDed; each term may match product `name`, `slug`, `description`, category `name` or an active collection `name`. Blank = no filter. |
| `category` | Category slug(s), comma-separated (max 10). Unknown slug -> empty result. |
| `collection` | Active collection slug(s), comma-separated. |
| `color` | `ColorVariant.slug`(s), comma-separated. Only active variants count. |
| `size` | `Size.code`(s), comma-separated. Only active variant sizes count. |
| `min_price`, `max_price` | Whole-unit integers, inclusive, applied to the **current** price (`sale_price` if set, else `price`). `min_price > max_price` -> 400. |
| `in_stock` | `true` -> only products with at least one purchasable `VariantSize` (active size, active variant) with `stock_quantity > 0`. `false`/absent -> no filter. |
| `sort` | `newest` (default), `price_asc`, `price_desc`, `name_asc`, `name_desc`. Anything else -> 400. Blank = default. Price sorts use current price. Every order ends in `id`, so pagination is deterministic. |
| `page`, `page_size` | DRF page-number pagination. Default 24, max 60. Response: `count`, `next`, `previous`, `results`. Out-of-range page -> 404. |

`color`, `size` and `in_stock` are evaluated against **one** `VariantSize` row: `color=black&size=m&in_stock=true` means
"a black, size-M unit that is in stock", not "has black somewhere and M somewhere".

Result item (card data only): `id, name, slug, price, sale_price, category{name,slug}, in_stock, image, colors[]`.
`image` is one representative image (first active variant by position, its primary image first, else lowest
position; `null` if none) as `{url, alt_text, width, height}` built via the CDN helper. `colors[]` are
`{name, slug, hex_color}` swatches of active variants. No sizes, SKUs, stock quantities, storage keys or descriptions.

Performance: filtering, search, price and ordering are SQL. Collections/variants/sizes are `Exists` sub-queries (no
join fan-out, so no duplicates and an exact `count`). In-stock flag and representative image are annotations
(correlated sub-queries, 1 image per product, not a prefetch of all images). A page costs 3 queries: count, products,
color swatches (regression-tested). Search is `icontains`; it is simple and index-free, fine at V1 catalog size. If
the catalog grows large, add `pg_trgm` GIN indexes (or Postgres full-text) without changing the API.

Intentionally unsupported: discounted-only (`on_sale`) filter and discount percentage sorting (discount rules are
still undecided; only the raw `sale_price` exists), relevance ranking, typo tolerance, facet counts, autocomplete,
filtering by arbitrary fields, `in_stock=false` meaning "out of stock only".

## Not implemented (for later agents)
write APIs, full admin (only bare `admin.site.register`), reviews, favorites,
orders, inventory logic, pricing/discount engine, image upload/conversion, caching.

### Filter vocabulary: `GET /api/catalog/filters/` (Agent 6, Session 2)
Public, read-only. Returns `{categories[{name,slug}], collections[{name,slug}], colors[{name,slug,hex_color}], sizes[{code,label}]}`
containing **only values that exist on published products** (active product + active category/variant/size/collection).
Fixed cost of 4 queries. Added so the storefront never offers fake filter values. Colors are de-duplicated by slug.

### Storefront (frontend) notes
Routes: `/[locale]/products` (listing) and `/[locale]/products/[slug]` (detail, `?color=<slug>` selects a variant).
All state is in the URL; filters/search are plain GET forms (`next/form`), sort/pagination/color are links. The listing remains server-rendered; `FilterDrawer`, `AddToCart` and the product-detail `ProductGallery` are client components.
The product gallery orders the primary image first and slides through the selected color's images. Selecting another color
keeps URL state and cross-fades to that color's gallery. The size selector shows exact stock quantities; zero-stock sizes
are red and disabled. After a size is selected, its measurement rows appear in a two-column table and update when the customer changes size; no table is shown when no measurements were entered. All storefront prices are formatted in Toman. E2E fixtures: `e2e/seed_catalog.py` (throwaway DB only).
