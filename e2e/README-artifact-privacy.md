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
  `scripts/sanitize-results.mjs` (rules in `scripts/lib/redaction.mjs`). It strips ANSI codes; redacts phone
  numbers and long opaque tokens; redacts the **value of any JSON property** whose name is sensitive (`otp`,
  `code`, `phone`, `cookie`, `token`, `password`, `secret`, `authorization`, `sessionid`, `csrftoken`, also
  camelCase/snake_case forms and `{"name": "Cookie", "value": ...}` pairs); redacts `key=value`, `key: value`,
  `"key":"value"` and escaped-JSON forms inside message text; and **withholds Playwright `Expected` / `Received`
  blocks entirely**, including multi-line object/array/string values and `- Expected` / `+ Received` diffs,
  plus call-log `unexpected value ...` and `locator resolved to <element ...>` echoes. Harmless state
  diagnostics (`Expected: visible`, `Received: hidden`, `Expected length: 2`) and the rest of the message
  (matcher, `Locator:`, `Call log:`, `Timeout:`, stack frames) are kept.
- It **fails closed on every path**. The output file is deleted before anything is read, and again on invalid
  or missing input, residual sensitive-shaped content (checked independently on the parsed output, then again
  on the file actually written), or a write error; parser error text is never printed because it can quote the
  input. The workflow uploads **only when the sanitize step's outcome is `success`** and also deletes any
  sanitized file otherwise, so a failed sanitization can never publish a stale or partial report. Never add
  `e2e/test-results`, traces, screenshots or videos to an upload path.
- `scripts/privacy-selftest.mjs` (synthetic values only; prints check names, never values) covers both CI
  failures seen on PR #28 (`unredacted otp value` and `Received value not withheld`), real Playwright message
  formats (LF/CRLF, nested/indented, multi-line, diff, call log), sensitive JSON properties, the fail-closed
  negative cases and every output-removal path. It runs in CI before the E2E suite; run it locally with
  `node scripts/privacy-selftest.mjs` before changing either script.
- The "backend logs on failure" step writes the raw log to a temp file and prints **only** the output of
  `scripts/redact-backend-log.mjs`: `DEV OTP delivery` lines (phone + OTP) are dropped, phone numbers and
  secret-style `key=value` / `key: value` / JSON pairs are redacted, tracebacks and status lines stay. It fails
  closed: if redaction errors or leaves sensitive-shaped content, a one-line notice is printed and the raw log is
  never shown.

## Known limits

- Redaction is pattern-based. It cannot recognise free-form text such as an address, which is why
  `Expected` / `Received` values are withheld instead.
- The Playwright `github` reporter prints failure messages straight to the Actions log; that output is not
  sanitized. Test data is synthetic and the CI stack is throwaway (`down -v` at the end), so keep it that way:
  never put real customer data in a test or fixture. Sanitizing the uploaded JSON does **not** sanitize the
  job log, and nothing here should be read as "all CI output is sanitized".
- The sanitizer rewrites values, not JSON object **key names**, test titles or locator text. A phone- or
  token-shaped key is caught by the post-check and fails the step (no artifact) instead of being rewritten; an
  arbitrary free-text secret inside a title or locator (`getByText('...')`) cannot be recognised at all. Keep
  such data out of titles and locators.
- Access logs still contain runner/container IP addresses.
- To debug a CI failure, reproduce it locally and use a local trace.
