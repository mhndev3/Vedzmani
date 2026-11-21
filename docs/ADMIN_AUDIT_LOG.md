# Admin audit log

- Captures authenticated active staff write attempts under `/api/admin/` and `/admin/` after the response.
- Stores actor ID, method/action, path without query string, inferred resource type and numeric resource ID, HTTP status, and timestamp.
- Exposes a read-only paginated/filterable feed at `GET /api/admin/audit-log/`, gated by `accounts.view_adminauditevent`.
- Includes the Persian RTL page at `/[locale]/admin-panel/audit-log`.
- Never stores request/response bodies, query strings, cookies, authorization headers, IP addresses, phone numbers, addresses, national IDs, passwords, OTPs, payment credentials, or session secrets.
- Audit persistence failures are logged without request data and do not replace the original business response. Alert on `admin_audit_event_write_failed`.
- This first version records request metadata, not field-level before/after diffs. It does not capture background jobs, direct database writes, or non-HTTP code paths.
- Migration `0005_admin_audit_event` depends on support-ticket migration `0004_support_tickets`. Back up and verify production DB before applying. No deploy included.
