#!/usr/bin/env node
// Self-test for scripts/sanitize-results.mjs and scripts/redact-backend-log.mjs. SYNTHETIC values only
// (fake phone numbers, fake OTP, fake tokens). Prints PASS/FAIL per check, never the values. Exit 1 on any FAIL.
// Usage (from e2e/): node scripts/privacy-selftest.mjs
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

// ---- backend log redaction ----
const log = [
  "INFO 2026-01-01 request started",
  `WARNING apps.accounts.delivery DEV OTP delivery: phone=${PHONES[0]} purpose=login code=${OTP}`,
  `ERROR checkout failed for ${PHONES[1]} ${PHONES[2]} (retry ${PHONES[3]}) ref ${PHONES[4]}`,
  `DEBUG Cookie: sessionid=${TOK}; csrftoken=${TOK}`,
  `DEBUG X-CSRFToken: ${TOK} authorization=Bearer ${TOK}`,
  `ERROR otp=${OTP} password=hunter2 code: ${OTP}`,
  "Traceback (most recent call last):",
  '  File "views.py", line 10, in post',
  "ValueError: stock not available",
].join("\n");
const r = spawnSync("node", [join(here, "redact-backend-log.mjs")], { input: log, encoding: "utf8" });
check("log: exit 0", r.status === 0);
for (const p of PHONES) check(`log: phone shape gone (${p.slice(0, 3)}…)`, !r.stdout.includes(p.replace(/\s/g, "")) && !r.stdout.includes(p));
check("log: OTP value gone", !r.stdout.includes(OTP));
check("log: fake token gone", !r.stdout.includes(TOK));
check("log: password value gone", !r.stdout.includes("hunter2"));
check("log: OTP delivery line dropped", !/DEV OTP delivery/.test(r.stdout));
check("log: diagnostics kept (traceback + error message)", r.stdout.includes("Traceback") && r.stdout.includes("ValueError: stock not available"));

// ---- fail-closed behaviour: unredactable shape must not be printed ----
const r2 = spawnSync("node", [join(here, "redact-backend-log.mjs")], { input: "ok\n", encoding: "utf8" });
check("log: benign input passes through", r2.status === 0 && r2.stdout.includes("ok"));

// ---- JSON report sanitizer ----
const msg =
  `Expected string: "12 Fake Street"\nReceived string: ""\nCall log:\n - Cookie: sessionid=${TOK}\n - phone ${PHONES[1]} ${PHONES[0]} otp=${OTP}`;
const report = {
  suites: [{ title: "a.spec.ts", specs: [{ id: "c5e1a0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7", title: "t", file: "a.spec.ts", tests: [{ status: "unexpected", results: [{ status: "failed", error: { message: msg } }] }] }] }],
  stats: { expected: 0, unexpected: 1, flaky: 0, skipped: 0 },
};
const src = join(tmp, "in.json");
const dst = join(tmp, "out.json");
writeFileSync(src, JSON.stringify(report));
const s = spawnSync("node", [join(here, "sanitize-results.mjs"), src, dst], { encoding: "utf8" });
const out = existsSync(dst) ? readFileSync(dst, "utf8") : "";
check("report: exit 0 and file written", s.status === 0 && out.length > 0);
check("report: token, phones, OTP, address gone", ![TOK, PHONES[0], PHONES[1], OTP, "Fake Street"].some((v) => out.includes(v)));
check("report: test id and status kept", out.includes("c5e1a0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7") && out.includes('"status": "failed"'));

rmSync(tmp, { recursive: true, force: true });
console.log(failed === 0 ? "ALL PASS" : `${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
