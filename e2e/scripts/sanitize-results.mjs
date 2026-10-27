#!/usr/bin/env node
// Writes a copy of the Playwright JSON report that is safe to upload as a CI artifact.
//
// Why: failure messages can echo typed values (phone numbers, OTP codes, delivery details) through
// `Expected:` / `Received:` lines, and call logs can quote cookies or tokens. Pattern-based redaction cannot
// recognise free-form text such as an address, so the `Expected`/`Received` value lines are withheld
// outright. It FAILS CLOSED: if anything sensitive-shaped survives, no output file is written and the step
// fails, so nothing is uploaded.
//
// Usage: node scripts/sanitize-results.mjs [results.json] [results.sanitized.json]
import { readFileSync, writeFileSync, rmSync } from "node:fs";

const [src = "results.json", dst = "results.sanitized.json"] = process.argv.slice(2);

const ANSI = /\u001b\[[0-9;]*m/g;
const ECHO_LINE = /^(\s*)(Expected|Received)(\s+\w+)?\s*:.*$/gim;
const SENSITIVE_KEY =
  "sessionid|csrftoken|csrf[-_]?token|x-csrftoken|set-cookie|cookie|authorization|bearer|token|otp|code|phone|password|secret";
const HEADER_LINE = /\b(cookie|set-cookie|authorization)(\s*[=:]\s*)[^\n]*/gi;
const KEY_VALUE = new RegExp(`\\b(${SENSITIVE_KEY})(\\s*[=:]\\s*)("?)(?:(?:Bearer|Basic|Token)\\s+)?[^\\s"';,&]+`, "gi");
const PHONE_INTL = /(?:\+|00)?98[\s-]?9\d{2}[\s-]?\d{3}[\s-]?\d{4}/g;
const PHONE_LOCAL = /(?<!\d)09\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)/g;
const LONG_TOKEN = /\b[A-Za-z0-9_-]{32,}\b/g;

function sanitizeString(s) {
  return s
    .replace(ANSI, "")
    .replace(ECHO_LINE, "$1$2$3: [value withheld]")
    .replace(HEADER_LINE, "$1$2[redacted]")
    .replace(KEY_VALUE, "$1$2$3[redacted]")
    .replace(PHONE_INTL, "[phone]")
    .replace(PHONE_LOCAL, "[phone]")
    .replace(LONG_TOKEN, "[token]");
}

function walk(node, key) {
  if (typeof node === "string") return key === "id" ? node : sanitizeString(node); // "id" = test hash, not data
  if (Array.isArray(node)) return node.map((n) => walk(n, key));
  if (node && typeof node === "object") {
    return Object.fromEntries(Object.entries(node).map(([k, v]) => [k, walk(v, k)]));
  }
  return node;
}

// Independent post-check on the serialised output (what would actually be uploaded).
function residualProblems(text) {
  const withoutIds = text.replace(/"id":\s*"[^"]*"/g, '"id":""');
  const problems = [];
  if (new RegExp(PHONE_INTL.source).test(withoutIds)) problems.push("international phone number");
  if (new RegExp(PHONE_LOCAL.source).test(withoutIds)) problems.push("local phone number");
  if (new RegExp(LONG_TOKEN.source).test(withoutIds)) problems.push("long opaque token");
  for (const m of withoutIds.matchAll(new RegExp(KEY_VALUE.source, "gi"))) {
    if (!/\[redacted\]/.test(m[0])) problems.push(`unredacted ${m[1].toLowerCase()} value`);
  }
  for (const m of withoutIds.replace(/\\n/g, "\n").matchAll(/^\s*(Expected|Received)(\s+\w+)?\s*:(.*)$/gim)) {
    if (!/^\s*\[value withheld\]\s*$/.test(m[3])) problems.push(`${m[1]} value not withheld`);
  }
  return [...new Set(problems)];
}

const raw = readFileSync(src, "utf8").replace(/^\uFEFF/, "");
const out = JSON.stringify(walk(JSON.parse(raw)), null, 2);
const problems = residualProblems(out);
rmSync(dst, { force: true });
if (problems.length > 0) {
  console.error(`sanitize-results: REFUSING to write ${dst}; residual sensitive-shaped content: ${problems.join(", ")}`);
  process.exit(1);
}
writeFileSync(dst, out);
console.log(`sanitize-results: wrote ${dst} (${out.length} bytes) from ${src}`);
