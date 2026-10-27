# E2E failure artifacts and privacy

**Playwright traces contain authentication tokens and personal data, and they cannot be redacted.** A trace
records `Cookie` / `Set-Cookie` headers (live `sessionid` and `csrftoken` values), typed OTP codes, phone
numbers, delivery name/address/postal code, and screenshots of every step.

## Local runs

- `trace` is `retain-on-failure` so a failing test can be debugged with `pnpm exec playwright show-trace`.
  Output goes to `e2e/test-results/`, which is gitignored.
- Never attach, upload, paste or commit a trace, screenshot or `test-results/` content (issues, PRs, chat, CI).
  Delete `e2e/test-results/` when you are done. A leaked local trace is only replayable against the local
  throwaway stack it came from, but treat it as a secret anyway.
- `screenshot` and `video` are always off (`playwright.config.ts`).

## CI (`.github/workflows/e2e.yml`)

- With `CI=true` the config turns **trace off** (plus screenshots and videos), so no raw debugging artifact
  is ever created on the runner.
- The **only** uploaded artifact is the single file `e2e/results.sanitized.json`, produced by
  `scripts/sanitize-results.mjs`: it strips ANSI codes, redacts phone numbers, cookie/token/OTP-style
  `key=value` pairs and long opaque tokens, and withholds the value on `Expected` / `Received` lines (those
  echo typed data on a failed assertion). It **fails closed**: if anything sensitive-shaped survives, no file
  is written and nothing is uploaded. Never add `e2e/test-results`, traces, screenshots or videos to
  an upload path.
- The "backend logs on failure" step writes the raw log to a temp file and prints **only** the output of
  `scripts/redact-backend-log.mjs`: `DEV OTP delivery` lines (phone + OTP) are dropped, phone numbers and
  secret-style `key=value` / `key: value` pairs are redacted, tracebacks and status lines stay. It fails closed:
  if redaction errors or leaves sensitive-shaped content, a one-line notice is printed and the raw log is never
  shown. Test both scripts with synthetic values only (see `scripts/*.test.mjs` if present) before changing them.

## Known limits

- Redaction is pattern-based. It cannot recognise free-form text such as an address, which is why
  `Expected` / `Received` values are withheld instead.
- The Playwright `github` reporter prints failure messages straight to the Actions log; that output is not
  sanitized. Test data is synthetic and the CI stack is throwaway (`down -v` at the end), so keep it that way:
  never put real customer data in a test or fixture.
- Access logs still contain runner/container IP addresses.
- To debug a CI failure, reproduce it locally and use a local trace.
