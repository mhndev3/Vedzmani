# Sign-in e2e (`tests/signin.spec.ts`, `tests/auth-redirect.spec.ts`)

`auth-redirect.spec.ts` is a pure unit test of the `?next=` sanitizer: no server needed.

`signin.spec.ts` runs against the Compose stack (Nginx -> Next + Django). Tests without
"(mocked response)" in the name call the real Django API. Tests under "real OTP flow" read the OTP
from the **test backend's log**, which only works because the dev settings use the DEV-ONLY
`ConsoleDelivery` (`DEV OTP delivery: phone=... code=...`). **That is not SMS delivery. No SMS
provider is configured, and these tests say nothing about real SMS.** They are skipped unless
`E2E_OTP_LOG_COMMAND` is set.

## Isolated test stack (never reuse a stack with real data)

1. `cp .env.example .env` and use throwaway values with a free `HTTP_PORT` (e.g. 8091); set
   `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` and `NEXT_PUBLIC_API_URL` to that origin.
2. Keep a **test-only** override file outside the repo, e.g. `compose.test.yml`:

   ```yaml
   services:
     postgres:
       ports: !reset []        # no host port
     backend:
       environment:
         OTP_REQUEST_IP_LIMIT: "1000"   # test stack only: many sign-ins come from one IP
         OTP_VERIFY_IP_LIMIT: "1000"
   ```

3. `docker compose -p vedzmani-agenti -f docker-compose.yml -f compose.test.yml up -d --build`
   (a distinct project name gives separate containers, network and database volume).
4. `... exec -T backend python manage.py migrate`, then seed the fixture catalog with
   `e2e/seed_catalog.py` (copy it into the container and `exec(open(...).read())` in `manage.py shell`, using
   `exec -T -e E2E_THROWAWAY_DB=1 backend ...`: the seeder refuses to run without that flag, which is your
   confirmation that this stack is disposable, not proof; see `README-purchase-journey.md`).
5. Run:

   ```
   cd e2e
   E2E_BASE_URL=http://localhost:8091 E2E_BROWSER_CHANNEL=msedge \
   E2E_OTP_LOG_COMMAND="docker compose -p vedzmani-agenti logs --no-color backend" \
   pnpm exec playwright test tests/signin.spec.ts
   ```

Never raise OTP limits in a shared or production environment. Each test uses its own phone number
because Django enforces a per-phone 60 s resend cooldown.
