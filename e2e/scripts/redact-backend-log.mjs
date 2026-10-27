#!/usr/bin/env node
// Redacts a backend log (stdin) before it is printed in the CI job log. Writes to stdout only.
//
// Why: the dev OTP delivery logs `DEV OTP delivery: phone=... purpose=... code=...`, and request/error lines can
// carry phone numbers or cookie/token-style values. Useful diagnostics (tracebacks, status lines, view names)
// are kept. It FAILS CLOSED: if anything sensitive-shaped survives the redaction, NOTHING is written to stdout
// and the exit code is 1, so the caller must never fall back to printing the original log.
//
// Usage: docker compose logs ... > raw.log; node scripts/redact-backend-log.mjs < raw.log > redacted.log
import { readFileSync } from "node:fs";

const OTP_DELIVERY_LINE = /DEV OTP delivery/i; // phone + OTP code on one line: dropped whole
const SENSITIVE_KEY =
  "sessionid|csrftoken|csrf[-_]?token|x-csrftoken|set-cookie|cookie|authorization|bearer|token|otp|code|phone|password|secret";
const HEADER_LINE = /\b(cookie|set-cookie|authorization)(\s*[=:]\s*)[^\n]*/gi;
const KEY_VALUE = new RegExp(`\\b(${SENSITIVE_KEY})(\\s*[=:]\\s*)("?)(?:(?:Bearer|Basic|Token)\\s+)?[^\\s"';,&]+`, "gi");
const PHONE_INTL = /(?:\+|00)?98[\s-]?9\d{2}[\s-]?\d{3}[\s-]?\d{4}/g;
const PHONE_LOCAL = /(?<!\d)09\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)/g;

const redactLine = (line) =>
  line
    .replace(HEADER_LINE, "$1$2[redacted]")
    .replace(KEY_VALUE, "$1$2$3[redacted]")
    .replace(PHONE_INTL, "[phone]")
    .replace(PHONE_LOCAL, "[phone]");

// Independent check on what would be printed.
const residual = (text) => {
  const problems = [];
  if (new RegExp(PHONE_INTL.source).test(text)) problems.push("international phone number");
  if (new RegExp(PHONE_LOCAL.source).test(text)) problems.push("local phone number");
  for (const m of text.matchAll(new RegExp(KEY_VALUE.source, "gi"))) {
    if (!/\[redacted\]/.test(m[0])) problems.push(`unredacted ${m[1].toLowerCase()} value`);
  }
  if (OTP_DELIVERY_LINE.test(text)) problems.push("OTP delivery line");
  return [...new Set(problems)];
};

const input = readFileSync(0, "utf8").replace(/\u001b\[[0-9;]*m/g, "");
const lines = input.split(/\r?\n/);
const kept = lines.filter((l) => !OTP_DELIVERY_LINE.test(l));
const out = kept.map(redactLine).join("\n");
const problems = residual(out);
if (problems.length > 0) {
  console.error(`redact-backend-log: REFUSING to print the log; residual sensitive-shaped content: ${problems.join(", ")}`);
  process.exit(1);
}
process.stdout.write(out.endsWith("\n") ? out : out + "\n");
console.error(`redact-backend-log: ok (${lines.length - kept.length} OTP delivery line(s) dropped)`);
