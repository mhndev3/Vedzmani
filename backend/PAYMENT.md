# SEP payment integration

## Inventory and confirmation policy
- Creating an order snapshots cart lines and prices, clears the cart, and does not reserve or decrement stock.
- On SEP callback, the backend resolves the attempt only from its server-created ResNum. Browser State, Status, and Amount are never proof of payment.
- The backend locks the payment attempt, then the order and each exact VariantSize row in ascending primary-key order. It calls SEP Verify while holding those locks and checks Success, ResultCode, RefNum, terminal number, OrginalAmount, and AffectiveAmount.
- Only after a fully matching server-side verification does it check stock. If any line is short, it does not decrement inventory; it marks the attempt out_of_stock and explicitly requests ReverseTransaction. Stock decrement and the paid/confirmed order transition commit together in one database transaction.
- Unique provider references and locked attempts make callback replays idempotent. A verified but mismatched transaction is sent to ReverseTransaction. If SEP reports a possibly collected transaction but verification details do not match, the attempt enters reversal_pending; repeated callbacks retry reversal without repeating fulfillment or verification. A database failure after provider verification also triggers a compensating reverse attempt.
- Inventory is per exact VariantSize (product + color + size).

## Public callback URL
After this PR is merged and deployed behind the production HTTPS domain, register this exact URL with SEP:

`https://vedzmani.ir/sep/cb/`

The short endpoint is an alias to the same `SepPaymentCallbackView` used by the original callback route. Payment initiation sends this short URL to SEP. It accepts SEP's browser `POST` form fields (`ResNum`, `RefNum`) and redirects the customer to the Persian payment-result page. A `GET` request returns `{"status":"ready"}` as a non-mutating reachability probe; it does not verify a transaction or mean live payments are enabled. The URL is not live until the backend release is deployed.

## SEP protocol
The adapter follows SEP OnlinePG technical guide v3.6: request a token from the classic token endpoint, send the returned Token to the classic payment page, receive ResNum and RefNum at the callback, then verify server-to-server. Verify is retried only when no response was received, never after a definite negative result. If all Verify attempts time out, the callback RefNum is preserved on the pending attempt and the scheduled verification retry re-enters the same callback service. A verified transaction that cannot be fulfilled is reversed. If the callback-time reverse is not confirmed, the attempt remains in `out_of_stock` or `reversal_pending`. The `retry_sep_reversals` management command safely retries those known provider references; it is dry-run by default and marks an attempt reversed only when SEP returns `Success=true` and `ResultCode=0`.
Order amounts are stored in Toman; SEP Amount is Rial, so the server converts the server-owned order total by multiplying by 10. Tipax freight is collect-on-delivery and is excluded from online payment. No amount is accepted from the browser.

## Configuration and go-live gate
- SEP_PAYMENT_ENABLED defaults to false in all environments and is explicitly false in production.
- SEP_TERMINAL_ID and endpoint configuration are server-only environment values; no secrets are committed or exposed to NEXT_PUBLIC variables.
- V1 shipping is Tipax collect-on-delivery. SEP charges only the server-owned order item total; freight is paid directly to Tipax on delivery and requires no shipping tariff configuration.
- Production ORDERS_ENABLED and NEXT_PUBLIC_ORDERS_ENABLED remain disabled. This PR does not change VPS settings or enable live payments.
- SEP has no real sandbox for this integration; tests mock the provider and never initiate a live transaction.
- Schedule both `python manage.py retry_sep_verifications --execute` and `python manage.py retry_sep_reversals --execute` periodically (for example, every 5 minutes). The verification command defaults to dry-run; it retries pending callbacks with a stored RefNum after a Verify timeout by calling the normal callback service. It can fulfill an order and decrement stock only after a complete matching server-side Verify and a fresh locked stock check. The reversal command defaults to dry-run and only retries attempts with a stored provider RefNum in `out_of_stock` or `reversal_pending`; it never verifies, fulfills, or decrements inventory.

## Safety
No PAN, CVV2, PIN2, or cardholder credentials are stored. The callback is CSRF-exempt because it is provider-originated; its fields are only lookup hints and server-to-server verification is mandatory.
