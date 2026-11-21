# Customer support tickets

Customers create and follow their own tickets from the profile's "پشتیبانی" section. Staff use the dedicated admin inbox at `/[locale]/admin-panel/support`.

## API
- Customer: `GET/POST /api/auth/support/tickets/`
- Customer detail/reply: `GET/POST /api/auth/support/tickets/<id>/`
- Staff inbox: `GET /api/admin/support/tickets/`
- Staff detail/status/reply: `GET/PATCH/POST /api/admin/support/tickets/<id>/`

## Permissions and privacy
- Customer endpoints require an authenticated non-staff customer and scope every read to `request.user`.
- Staff inbox requires `accounts.view_supportticket`.
- Status changes require `accounts.change_supportticket`.
- Staff replies and internal notes require `accounts.add_supportticketmessage`.
- Internal notes are excluded from customer responses.
- Customer directory and order PII permissions do not grant access to support tickets.
- Ticket messages are plain text only; attachments are not accepted.
- No delete endpoint is provided.

## Statuses
`open`, `in_progress`, `waiting_customer`, `resolved`, `closed`.

This feature is independent of checkout, order lifecycle, inventory, shipping rates, OTP providers, and SEP payment activation.
