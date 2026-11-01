# Storefront V2 implementation notes

- Product favorites are customer-owned records. The authenticated catalog API never returns another customer's saved products.
- Production order creation is disabled by default until the payment provider and its verified callback flow are configured. The backend returns 503 even if a client bypasses the disabled UI.
- The current cart and checkout API are account-bound. A complete guest-order flow needs a guest cart identity, delivery phone verification/lookup policy, and secure order access. It is intentionally not simulated by attaching anonymous requests to arbitrary accounts.
- Catalog media swaps and the single-unit stock increase must be verified against the real product/variant IDs before applying to production. The PR does not mutate live product data.
