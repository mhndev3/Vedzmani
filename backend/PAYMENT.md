# SEP payment integration

## Inventory and confirmation policy
- Creating an order snapshots cart lines and prices, clears the cart, and does not reserve or decrement stock.
- On SEP callback, the backend resolves the attempt only from its server-created ResNum. Browser State, Status, and Amount are never proof of payment.
- The backend locks the order and each exact VariantSize row in ascending primary-key order. If any line is short, it does not call VerifyTransaction; the attempt is marked out_of_stock and SEP's unverified-transaction timeout reverses the payment automatically.
- If stock is sufficient, the backend calls SEP Verify while holding the row locks, checks Success, ResultCode, RefNum, terminal number, OrginalAmount, and AffectiveAmount, then decrements stock and marks the order confirmed/paid in one database transaction.
- Unique provider references and locked attempts make callback replays idempotent. A verified but mismatched transaction is sent to ReverseTransaction; a database failure after provider verification also triggers a compensating reverse attempt.
- Inventory is per exact VariantSize (product + color + size).

## SEP protocol
The adapter follows SEP OnlinePG technical guide v3.6: request a token from the classic token endpoint, send the returned Token to the classic payment page, receive ResNum and RefNum at the callback, then verify server-to-server. Verify is retried only when no response was received, never after a definite negative result. A verified transaction that cannot be fulfilled is reversed.
Order amounts are stored in Toman; SEP Amount is Rial, so the server converts by multiplying by 10. No amount is accepted from the browser.

## Configuration and go-live gate
- SEP_PAYMENT_ENABLED defaults to false in all environments and is explicitly false in production.
- SEP_TERMINAL_ID and endpoint configuration are server-only environment values; no secrets are committed or exposed to NEXT_PUBLIC variables.
- Real payments must remain disabled until the owner defines and implements shipping charges. Order.total currently excludes shipping and is not the final payable amount.
- Production ORDERS_ENABLED and NEXT_PUBLIC_ORDERS_ENABLED remain disabled. This PR does not change VPS settings or enable live payments.
- SEP has no real sandbox for this integration; tests mock the provider and never initiate a live transaction.

## Safety
No PAN, CVV2, PIN2, or cardholder credentials are stored. The callback is CSRF-exempt because it is provider-originated; its fields are only lookup hints and server-to-server verification is mandatory.
