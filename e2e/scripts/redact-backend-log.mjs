#!/usr/bin/env node
// Redacts a backend log (stdin) before it is printed in the CI job log. Writes to stdout only.
//
// Why: the dev OTP delivery logs `DEV OTP delivery: phone=... purpose=... code=...`, and request/error lines can
// carry phone numbers or cookie/token-style values, including as JSON (`{"otp": "..."}`). Useful diagnostics
// (tracebacks, status lines, view names) are kept. It FAILS CLOSED: if anything sensitive-shaped survives the
// redaction, NOTHING is written to stdout and the exit code is 1, so the caller must never fall back to printing
// the original log. Rules are shared with sanitize-results.mjs (scripts/lib/redaction.mjs).
//
// Usage: docker compose logs ... > raw.log; node scripts/redact-backend-log.mjs < raw.log > redacted.log
import { readFileSync } from "node:fs";
import { normalizeText, redactSensitiveValues, sensitiveValueProblems } from "./lib/redaction.mjs";

const OTP_DELIVERY_LINE = /DEV OTP delivery/i; // phone + OTP code on one line: dropped whole

// Independent check on what would be printed.
const residual = (text) => {
  const problems = sensitiveValueProblems(text);
  if (OTP_DELIVERY_LINE.test(text)) problems.push("OTP delivery line");
  return [...new Set(problems)];
};

const input = normalizeText(readFileSync(0, "utf8"));
const lines = input.split("\n");
const kept = lines.filter((l) => !OTP_DELIVERY_LINE.test(l));
const out = kept.map(redactSensitiveValues).join("\n");
const problems = residual(out);
if (problems.length > 0) {
  console.error(`redact-backend-log: REFUSING to print the log; residual sensitive-shaped content: ${problems.join(", ")}`);
  process.exit(1);
}
process.stdout.write(out.endsWith("\n") ? out : out + "\n");
console.error(`redact-backend-log: ok (${lines.length - kept.length} OTP delivery line(s) dropped)`);
