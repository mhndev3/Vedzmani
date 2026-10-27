#!/usr/bin/env node
// Self-test for scripts/sanitize-results.mjs and scripts/redact-backend-log.mjs. SYNTHETIC values only
// (fake phone numbers, fake OTP, fake tokens, fake address). Prints PASS/FAIL per check, never the values.
// Exit 1 on any FAIL.   Usage (from e2e/): node scripts/privacy-selftest.mjs
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, readFileSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tmp = mkdtempSync(join(tmpdir(), "privacy-selftest-"));
let failed = 0;
const check = (name, ok) => {
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}`);
};

const TOK = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"; // fake, 36 chars
const PHONES = ["+989120000001", "09120000002", "00989120000003", "+98 912 000 0004", "989120000005"];
const OTP = "654321";
const ADDR = "12 Fake Street";
const ID = "c5e1a0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7";
const SECRETS = [TOK, ...PHONES.slice(0, 2), OTP, ADDR, "hunter2", "s3cr3t-value", "cookie-value-1"];
const leaks = (out) => SECRETS.filter((v) => out.includes(v));

// ---------- backend log redaction ----------
const log = [
  "INFO 2026-01-01 request started",
  `WARNING apps.accounts.delivery DEV OTP delivery: phone=${PHONES[0]} purpose=login code=${OTP}`,
  `ERROR checkout failed for ${PHONES[1]} ${PHONES[2]} (retry ${PHONES[3]}) ref ${PHONES[4]}`,
  `DEBUG Cookie: sessionid=${TOK}; csrftoken=${TOK}`,
  `DEBUG X-CSRFToken: ${TOK} authorization=Bearer ${TOK}`,
  `ERROR otp=${OTP} password=hunter2 code: ${OTP}`,
  `DEBUG body {"otp":"${OTP}","phone":"${PHONES[1]}","password":"hunter2"}`,
  "Traceback (most recent call last):",
  '  File "views.py", line 10, in post',
  "ValueError: stock not available",
].join("\n");
const r = spawnSync("node", [join(here, "redact-backend-log.mjs")], { input: log, encoding: "utf8" });
check("log: exit 0", r.status === 0);
for (const p of PHONES) check(`log: phone shape gone (${p.slice(0, 3)}…)`, !r.stdout.includes(p.replace(/\s/g, "")) && !r.stdout.includes(p));
check("log: OTP value gone", !r.stdout.includes(OTP));
check("log: fake token gone", !r.stdout.includes(TOK));
check("log: password value gone (key=value and JSON)", !r.stdout.includes("hunter2"));
check("log: OTP delivery line dropped", !/DEV OTP delivery/.test(r.stdout));
check("log: diagnostics kept (traceback + error message)", r.stdout.includes("Traceback") && r.stdout.includes("ValueError: stock not available"));
const r2 = spawnSync("node", [join(here, "redact-backend-log.mjs")], { input: "ok\n", encoding: "utf8" });
check("log: benign input passes through", r2.status === 0 && r2.stdout.includes("ok"));

// ---------- JSON report sanitizer: helpers ----------
const mkReport = (error, extra = {}) => ({
  suites: [{ title: "a.spec.ts", specs: [{ id: ID, title: "t", file: "a.spec.ts", tests: [{ status: "unexpected", results: [{ status: "failed", duration: 12, error, ...extra }] }] }] }],
  stats: { expected: 0, unexpected: 1, flaky: 0, skipped: 0 },
});
let n = 0;
function sanitize(report, { rawText, pre } = {}) {
  const src = join(tmp, `in${++n}.json`);
  const dst = join(tmp, `out${n}.json`);
  writeFileSync(src, rawText ?? JSON.stringify(report));
  if (pre) writeFileSync(dst, pre);
  const s = spawnSync("node", [join(here, "sanitize-results.mjs"), src, dst], { encoding: "utf8" });
  return { s, dst, src, out: existsSync(dst) ? readFileSync(dst, "utf8") : null, tmpLeft: existsSync(`${dst}.tmp`) };
}

// Original report check (address/phones/otp/token in an Expected/Received + call log message)
const msg = `Expected string: "${ADDR}"\nReceived string: ""\nCall log:\n - Cookie: sessionid=${TOK}\n - phone ${PHONES[1]} ${PHONES[0]} otp=${OTP}`;
let t = sanitize(mkReport({ message: msg }));
check("report: exit 0 and file written", t.s.status === 0 && t.out && t.out.length > 0);
check("report: token, phones, OTP, address gone", t.out && leaks(t.out).length === 0);
check("report: test id and status kept", t.out && t.out.includes(ID) && t.out.includes('"status": "failed"'));

// ---------- REGRESSION, CI failure 1: "unredacted otp value" ----------
// Quoted values after a sensitive key inside message text. The old post-check re-parsed JSON-escaped text (\")
// and flagged an already-redacted value; the old redactor also missed JSON-shaped text.
const kvMsg = [
  `step failed otp: "${OTP}"`,
  `retry code='${OTP}' password="hunter2"`,
  `body {"otp":"${OTP}","phone":"${PHONES[1]}","secret":"s3cr3t-value"}`,
  `double-encoded {\\"otp\\":\\"${OTP}\\",\\"password\\":\\"hunter2\\"}`,
  `url /verify?code=${OTP}&phone=${PHONES[0]}&next=/cart`,
  `compound access_token=${TOK} phoneNumber: ${PHONES[1]} otpCode=${OTP}`,
].join("\n");
t = sanitize(mkReport({ message: kvMsg }));
check("CI#1 otp quoted/JSON text: sanitizer exits 0 (no false 'unredacted otp value')", t.s.status === 0 && !/unredacted/.test(t.s.stderr));
check("CI#1 otp quoted/JSON text: all values gone", t.out !== null && leaks(t.out).length === 0);
check("CI#1 otp quoted/JSON text: non-sensitive text kept (next=/cart, step failed)", t.out !== null && t.out.includes("next=/cart") && t.out.includes("step failed"));

// ---------- REGRESSION, CI failure 2: "Received value not withheld" ----------
// Real Playwright formats: LF, CRLF, nested/indented, multi-line object/array values, diff block, call log.
const pwLF =
  `Error: expect(locator).toHaveValue(expected)\n\nLocator: getByLabel('Address')\nExpected string: "${ADDR}"\nReceived string: "${PHONES[1]}"\nTimeout: 5000ms\n\nCall log:\n  - Expect "toHaveValue" with timeout 5000ms\n  - waiting for getByLabel('Address')\n    9 × locator resolved to <input id="addr" value="${ADDR}"/>\n      - unexpected value "${ADDR}"\n`;
const pwCRLF = pwLF.replace(/\n/g, "\r\n");
const pwNested = pwLF.split("\n").map((l) => (l ? "    " + l : l)).join("\n");
const pwMultiObject =
  `Error: expect(received).toEqual(expected) // deep equality\n\nExpected: {"addr": "${ADDR}",\n  "phone": "${PHONES[1]}"}\nReceived: {\n  "addr": "x",\n  "phone": "${PHONES[0]}",\n  "otp": "${OTP}"\n}\n\n- Expected\n+ Received\n\n  {\n-   "addr": "${ADDR}",\n+   "addr": "x",\n  }\n    at /repo/e2e/tests/a.spec.ts:10:5\n`;
const pwArray = `Error: expect(received).toHaveLength(expected)\n\nExpected length: 2\nReceived length: 3\nReceived array: [\n  "${ADDR}",\n  "${PHONES[1]}"\n]\n`;
const pwStrict = `Error: strict mode violation: getByRole('textbox') resolved to 2 elements:\n    1) <input name="phone" value="${PHONES[1]}"/> aka getByLabel('Phone')\n    2) <input name="otp" value="${OTP}"/> aka getByLabel('Code')\n`;
const pwState = `Error: expect(locator).toBeVisible()\n\nLocator: getByRole('button', { name: 'Pay' })\nExpected: visible\nReceived: hidden\nTimeout: 5000ms\n`;
for (const [name, message] of Object.entries({ LF: pwLF, CRLF: pwCRLF, "nested/indented": pwNested, "multi-line object + diff": pwMultiObject, "multi-line array": pwArray, "strict-mode element dump": pwStrict })) {
  t = sanitize(mkReport({ message, stack: message }));
  check(`CI#2 playwright ${name}: exit 0, file written`, t.s.status === 0 && t.out !== null);
  check(`CI#2 playwright ${name}: no echoed value survives`, t.out !== null && leaks(t.out).length === 0);
}
t = sanitize(mkReport({ message: pwLF }));
check("CI#2 diagnostics kept: error title, matcher, Locator, Call log, Timeout", t.out !== null && ["toHaveValue(expected)", "Locator: getByLabel('Address')", "Call log:", "Timeout: 5000ms", "Expected string: [value withheld]", "Received string: [value withheld]"].every((x) => t.out.includes(x)));
t = sanitize(mkReport({ message: pwMultiObject }));
check("CI#2 stack frame after a withheld diff is kept", t.out !== null && t.out.includes("a.spec.ts:10:5") && t.out.includes("[diff withheld]"));
t = sanitize(mkReport({ message: pwState }));
check("CI#2 safe state diagnostics kept (Expected: visible / Received: hidden)", t.out !== null && t.out.includes("Expected: visible") && t.out.includes("Received: hidden"));
t = sanitize(mkReport({ message: pwArray }));
check("CI#2 length/count diagnostics kept", t.out !== null && t.out.includes("Expected length: 2") && t.out.includes("Received length: 3"));

// ---------- sensitive JSON PROPERTIES (not only key=value text) ----------
const propReport = mkReport(
  { message: "plain failure", otp: OTP, code: OTP, phone: PHONES[1], details: { cookie: "cookie-value-1", nested: [{ token: TOK }, { password: "hunter2" }], secret: "s3cr3t-value" } },
  {
    headers: [{ name: "Cookie", value: "cookie-value-1" }, { name: "Accept", value: "text/html" }],
    phoneNumber: PHONES[0],
    accessToken: TOK,
    statusCode: 500,
  },
);
t = sanitize(propReport);
check("props: exit 0 and file written", t.s.status === 0 && t.out !== null);
check("props: otp/code/phone/cookie/token/password/secret property values gone (nested, arrays, camelCase)", t.out !== null && leaks(t.out).length === 0);
check("props: header pair named Cookie redacted via its name, others kept", t.out !== null && !t.out.includes("cookie-value-1") && t.out.includes("text/html"));
const parsedProps = t.out ? JSON.parse(t.out) : null;
const res0 = parsedProps?.suites?.[0]?.specs?.[0]?.tests?.[0]?.results?.[0];
check("props: sensitive properties become [redacted] and keys stay", res0?.error?.otp === "[redacted]" && res0?.error?.details?.nested?.[0]?.token === "[redacted]" && res0?.statusCode === "[redacted]");
check("props: non-sensitive properties untouched (status, duration, title, id)", res0?.status === "failed" && res0?.duration === 12 && parsedProps?.suites?.[0]?.specs?.[0]?.title === "t" && parsedProps?.suites?.[0]?.specs?.[0]?.id === ID);

// ---------- NEGATIVE: fails closed, leaves no output ----------
// An object KEY that is phone-shaped is not rewritten by the redactor, so the independent post-check must catch it.
const stale = '{"stale":"previous run output"}';
t = sanitize({ suites: [], [PHONES[1]]: "x" }, { pre: stale });
check("negative: unredactable phone-shaped key -> exit 1", t.s.status === 1);
check("negative: no output artifact left behind (stale file removed, no .tmp)", t.out === null && !t.tmpLeft);
check("negative: message names a problem class but never prints the value", /REFUSING to write/.test(t.s.stderr) && !t.s.stderr.includes(PHONES[1]) && !t.s.stdout.includes(PHONES[1]));
t = sanitize({ suites: [], [TOK]: 1 }, { pre: stale });
check("negative: long opaque token as a key -> exit 1 and no output", t.s.status === 1 && t.out === null);

// ---------- every failure path removes the output ----------
t = sanitize(null, { rawText: `{"message": "${TOK} not json`, pre: stale });
check("failure path: invalid JSON -> exit 1, stale output removed", t.s.status === 1 && t.out === null);
check("failure path: parser error text (can quote input) is never printed", !t.s.stderr.includes(TOK) && !t.s.stdout.includes(TOK));
{
  const dst = join(tmp, "missing-out.json");
  writeFileSync(dst, stale);
  const s = spawnSync("node", [join(here, "sanitize-results.mjs"), join(tmp, "does-not-exist.json"), dst], { encoding: "utf8" });
  check("failure path: missing source -> exit 1, stale output removed", s.status === 1 && !existsSync(dst));
}
{
  const same = join(tmp, "same.json");
  writeFileSync(same, JSON.stringify(mkReport({ message: "m" })));
  const s = spawnSync("node", [join(here, "sanitize-results.mjs"), same, same], { encoding: "utf8" });
  check("failure path: source == destination refused and the source is NOT destroyed", s.status === 1 && existsSync(same));
}
t = sanitize(mkReport({ message: "ok" }), { pre: stale });
check("success path: a stale output is replaced by the new sanitized report", t.s.status === 0 && t.out !== null && !t.out.includes("previous run output") && !t.tmpLeft);

rmSync(tmp, { recursive: true, force: true });
console.log(failed === 0 ? "ALL PASS" : `${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
