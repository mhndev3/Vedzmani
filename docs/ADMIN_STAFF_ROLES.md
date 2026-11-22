# Admin staff roles and access control

The custom Persian workspace manages existing non-superuser staff accounts through Django's native Groups and Permissions. It does not create staff accounts, set passwords, grant superuser status, or change customer accounts.

## Access boundary

- Every endpoint requires an authenticated, active staff superuser.
- A session marked as established through customer OTP verification is rejected. Staff access management must use the existing password-authenticated admin session.
- Staff list and role-management APIs are not available to ordinary staff, customers, or OTP-only sessions.
- Superuser accounts are never listed as assignable staff and cannot be modified through this API.
- The built-in /admin/ OTP/password security gate remains unchanged.

## Workspace

- GET /api/admin/staff/: list existing active/inactive non-superuser staff identifiers and safe role summaries. Phone numbers are not returned.
- GET /api/admin/staff/roles/: list manageable roles and the curated permission catalogue.
- POST /api/admin/staff/roles/: create a role.
- PATCH /api/admin/staff/roles/<id>/: rename a role and/or replace its managed permissions.
- DELETE /api/admin/staff/roles/<id>/: delete only an unused role.
- PATCH /api/admin/staff/<id>/roles/: replace the assigned roles for an existing non-superuser staff account.

## Permission allowlist

The role editor exposes only permissions needed by the current admin workspace across accounts/support, catalog/content, read-only orders/shipping, and inventory adjustments. It does not expose Django auth/group/permission administration, user add/change/delete, superuser controls, payment permissions, or arbitrary app permissions.

Groups carrying permissions outside this allowlist are not editable or assignable through the custom workspace. This prevents an existing powerful Django group from being silently re-used as an ordinary workspace role.

## Audit

Role creation, role edits/deletion, and staff role assignment write append-only audit events with a sanitized details.before and details.after snapshot. The snapshots contain only role IDs, role names, and allowlisted permission keys. The generic audit middleware skips these routes to avoid duplicate entries.

The audit feed remains read-only and permission-gated. Existing generic audit events continue to contain request metadata only; this change does not claim to provide full field-level diffs for every catalog or content mutation.

## Safety

- Role deletion is rejected while any user is assigned to the group.
- Staff assignment accepts only existing non-superuser staff accounts and manageable roles.
- No endpoint can promote a customer to staff or grant superuser status.
- Orders remain read-only; PII requires its separate permission. Payment and order feature flags are unaffected.
- Production deployment is separate and is not part of this change.
