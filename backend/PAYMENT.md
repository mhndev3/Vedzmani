# SEP payment integration

## Inventory and confirmation policy
- Creating an order snapshots cart lines and prices, clears the cart, and does not reserve or decrement stock.
- On SEP callback, the backend resolves the attempt only from its server-created ResNum. Browser State, Status, and Amount are never proof of payment.
- The backend locks the order and each exact VariantSize row in ascending primary-key order. If any line is short, it does not call VerifyTransaction; the attempt is marked out_of_stock and SEP's unverified-transaction timeout reverses the payment automatically.
- If stock is sufficient, the backend calls SEP Verify while holding the row locks, checks Success, ResultCode, RefNum, terminal number, OrginalAmount, and AffectiveAmount, then decrements stock and marks the order confirmed/paid in one database transaction.
- Unique provider references and locked attempts make callback replays idempotent. A verified but mismatched transaction is sent to ReverseTransaction; a database failure after provider verification also triggers a compensating reverse attempt.
- Inventory is per exact VariantSize (product + color + size).

## Public callback URL
After this PR is merged and deployed behind the production HTTPS domain, register this exact URL with SEP:\n\n`https://vedzmani.ir/api/orders/payment/sep/callback/`\n\nThe endpoint accepts SEP's browser `POST` form fields (`ResNum`, `RefNum`) and redirects the customer to the Persian payment-result page. A `GET` request returns `{"status":"ready"}` as a non-mutating reachability probe; it does not verify a transaction or mean live payments are enabled. The URL is not live until the backend release is deployed.\n\n## SEP protocol\nThe adapter follows SEP OnlinePG technical guide v3.6: request a token from the classic token endpoint, send the returned Token to the classic payment page, receive ResNum and RefNum at the callback, then verify server-to-server. Verify is retried only when no response was received, never after a definite negative result. A verified transaction that cannot be fulfilled is reversed.
Order amounts are stored in Toman; SEP Amount is Rial, so the server converts the server-owned order total plus shipping by multiplying by 10. No amount is accepted from the browser.

## Configuration and go-live gate
- SEP_PAYMENT_ENABLED defaults to false in all environments and is explicitly false in production.
- SEP_TERMINAL_ID and endpoint configuration are server-only environment values; no secrets are committed or exposed to NEXT_PUBLIC variables.
- SEP_SHIPPING_AMOUNT_TOMAN must be explicitly configured (zero only when shipping is intentionally free). The current setting supports a fixed shipping amount; real payments must remain disabled if shipping varies by destination until that rule is implemented.
- Production ORDERS_ENABLED and NEXT_PUBLIC_ORDERS_ENABLED remain disabled. This PR does not change VPS settings or enable live payments.
- SEP has no real sandbox for this integration; tests mock the provider and never initiate a live transaction.

## Safety
No PAN, CVV2, PIN2, or cardholder credentials are stored. The callback is CSRF-exempt because it is provider-originated; its fields are only lookup hints and server-to-server verification is mandatory.
