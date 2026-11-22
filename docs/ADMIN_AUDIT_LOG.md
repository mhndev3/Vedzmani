# Admin audit log

- Captures authenticated active staff write attempts under `/api/admin/` and `/admin/` after the response.
- Stores actor ID, method/action, path without query string, inferred resource type and numeric resource ID, HTTP status, and timestamp.\n- Staff-role and role-assignment changes include curated before/after snapshots containing only role IDs, role names, and allowlisted permission keys; no phone number, password, customer data, or request body is recorded.
- Exposes a read-only paginated/filterable feed at `GET /api/admin/audit-log/`, gated by `accounts.view_adminauditevent`.
- Includes the Persian RTL page at `/[locale]/admin-panel/audit-log`.
- Never stores request/response bodies, query strings, cookies, authorization headers, IP addresses, phone numbers, addresses, national IDs, passwords, OTPs, payment credentials, or session secrets.
- Audit persistence failures are logged without request data and do not replace the original business response. Alert on `admin_audit_event_write_failed`.
- Other admin mutations still record request metadata only; field-level before/after diffs for catalog/content/customer/order records are not yet implemented. The log does not capture background jobs, direct database writes, or non-HTTP code paths.
- Migration `0005_admin_audit_event` depends on support-ticket migration `0004_support_tickets`; migration `0006_admin_audit_details` adds the safe JSON details field. Back up and verify production DB before applying. No deploy included.
