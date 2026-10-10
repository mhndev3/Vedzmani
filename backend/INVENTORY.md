# Inventory foundation (Agent 10, Session 1)

App: `backend/apps/inventory`. PostgreSQL is the source of truth; Redis never holds stock.

```
staff (Django admin) -> services.adjust_stock -> VariantSize.stock_quantity  (+ InventoryAdjustment audit row)
                                  ^ same row lock as
order checkout (orders.services.create_order) -> VariantSize.stock_quantity  (recorded by Order/OrderItem)
```

`catalog.VariantSize.stock_quantity` is still the single current quantity. This session adds the controlled way
for **staff** to change it, plus an append-only history. Order checkout is unchanged (it still decrements under its
own `select_for_update`, and is not recorded as an adjustment).

## Model: `InventoryAdjustment`
| Field | Notes |
|---|---|
| `variant_size` | FK `catalog.VariantSize`, `PROTECT` (history cannot be orphaned) |
| `quantity_change` | signed integer, DB check `!= 0` (`+N` adds, `-N` removes) |
| `stock_after` | quantity right after this change (lets history be replayed and drift detected) |
| `reason` | required text, max 255, stored trimmed |
| `created_by` | FK user, `PROTECT`, nullable only for non-user (system/script) adjustments; the admin always sets it |
| `created_at` | server timestamp |

Ordered newest first; index `(variant_size, -created_at)` for one item's history. Migration `inventory/0001_initial`
only creates this table; no existing rows are touched and no opening-balance rows are backfilled.

## Service: `services.adjust_stock(*, variant_size_id, quantity_change, reason, created_by=None)`
One `transaction.atomic` block:
1. Validate (integer, non-zero, in range, non-blank reason <= 255, known id) **before** any lock.
2. `SELECT ... FOR UPDATE OF catalog_variantsize` on that one row (same style as checkout, so adjustments and orders
   serialize on the same row).
3. `new = locked stock + change` from the locked database value; callers never pass the resulting stock.
   `new < 0` -> `StockWouldGoNegative` (409 `insufficient_stock`); above the DB integer range -> `InvalidAdjustment`.
4. Guarded `UPDATE` (compare-and-set on the locked value) and `updated_at` bump.
5. Insert the `InventoryAdjustment`. Any exception rolls back the stock change and the audit row together.
Three statements per call (lock+read, update, insert). Bad input raises `InvalidAdjustment` (400 `invalid_adjustment`).
Returns the audit row. Exceptions are DRF `APIException`s like the cart/order services (the admin turns them into
messages, never a 500). It locks a single row, so there is no lock-ordering issue; a future multi-row operation
must lock in primary-key order like checkout.

**Rule:** staff/business code must change stock only through this service (or checkout). Do not write
`stock_quantity` directly. There is no public API for adjustments in V1.

## Admin
- `VariantSize.stock_quantity` is **read-only** on the VariantSize page, the VariantSize changelist and the size
  inline on the ColorVariant page. A new size starts at 0; posted stock values are ignored (tested). Staff who may
  add adjustments see an "Adjust stock" link on the VariantSize page (prefills the adjustment form).
- **Inventory adjustments** (`/admin/inventory/inventoryadjustment/`): add form = stock item (autocomplete), signed
  quantity, reason. `save_model` calls the service; a lost race becomes an error message. The friendly "only N in
  stock" form error is an unlocked pre-check; the service re-checks under the lock.
- History columns: time, SKU, product, color, size, change, stock after, reason, who (staff phone). Searchable by
  SKU, product, reason, staff phone. Constant query count (tested).
- Permissions (stock Django model permissions, no custom RBAC): `inventory.add_inventoryadjustment` creates,
  `inventory.view_inventoryadjustment` reads. **No change or delete for anyone, superusers included.**
  The stock-item picker also needs `catalog.view_variantsize`. Add alone does not expose the history.

## Not implemented (by design)
Automatic restocking / order cancellation, reservations, an adjustments API or frontend, opening-balance backfill,
bulk or CSV adjustments, multi-location stock, low-stock alerts, analytics.

## Caveats / handoff
- `PROTECT`: a product, color variant or size that has adjustments (or orders) cannot be deleted through the admin;
  Django shows the protected-objects page. Deactivate (`is_active=False`) instead. The same applies to deleting a
  staff user who made adjustments.
- Existing stock has no opening history: the first adjustment's `stock_after` is the first recorded balance.
- Anyone with raw database or shell access can still write the column; the guarantee covers the admin and service.
- Any future restock-on-cancel must call `adjust_stock` (or share its lock) and define its own reason/actor.

## Tests
`tests/test_inventory_service.py` (positive/negative/zero-floor, only-own-row, audit fields and trimming, optional
actor, rejection of negative/invalid quantity/reason/id/overflow, `FOR UPDATE OF` + 3-statement shape, rollback with
a failing audit insert and a failing stock update, outer-transaction safety, checkout compatibility, and real-thread
PostgreSQL concurrency: no oversell, mixed +/- with a replayable audit trail, adjustments racing real checkouts) and
`tests/test_inventory_admin.py` (create/reject via admin, lost-race handling, picker, history content/search/N+1,
read-only detail, no change/delete for superusers, permission matrix, and stock read-only on every catalog admin
surface). `tests/test_admin_catalog.py::test_variant_page_can_add_size_but_stock_cannot_be_set_directly` replaces the old
stock-on-create test.
