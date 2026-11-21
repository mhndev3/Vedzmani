# Admin catalog taxonomy

The custom Persian RTL workspace at `/[locale]/admin-panel/catalog/taxonomy` manages existing catalog categories and collections through the staff API.

## Capabilities

- List and search categories and collections.
- Create and edit names and unique slugs.
- Activate and deactivate records without hard deletion.
- Change display order using the existing `position` field.
- Preserve product-to-category and product-to-collection relations.

## API and security

Uses the existing endpoints:

- `/api/admin/catalog/categories/`
- `/api/admin/catalog/collections/`

The backend remains authoritative for active staff status, Django model permissions, session authentication, and CSRF. The UI does not add a bypass or hard-delete operation. A user needs the relevant view/add/change permissions for each model.

## Scope

No schema migration, public storefront change, product reassignment, inventory adjustment, order, payment, or production configuration change is included. Product and variant measurement rows remain managed through their existing permission-checked API and are a separate UI phase.
