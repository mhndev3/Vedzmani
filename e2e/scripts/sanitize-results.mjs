#!/usr/bin/env node
// Writes a copy of the Playwright JSON report that is safe to upload as a CI artifact.
//
// Why: failure messages can echo typed values (phone numbers, OTP codes, delivery details) through
// `Expected:` / `Received:` blocks, call logs can quote element values, cookies or tokens, and report objects can
// carry sensitive values as JSON properties (`"otp": "..."`). Pattern-based redaction cannot recognise
// free-form text such as an address, so `Expected` / `Received` blocks (including multi-line values and diffs)
// are withheld outright. See scripts/lib/redaction.mjs for the rules.
//
// FAILS CLOSED, on every path: the destination file is deleted FIRST (before reading or parsing anything), and
// again on any error, unreadable/invalid input, residual sensitive-shaped content, or write failure. A stale or
// partial output can therefore never survive a failed run. Error text from the JSON parser is never printed
// because it can quote input. Exit code 0 only when a verified file was written.
//
// Usage: node scripts/sanitize-results.mjs [results.json] [results.sanitized.json]
import { readFileSync, writeFileSync, renameSync, rmSync } from "node:fs";
import { resolve } from "node:path";
import { redactTree, treeProblems, serializedProblems } from "./lib/redaction.mjs";

const [src = "results.json", dst = "results.sanitized.json"] = process.argv.slice(2);
const tmp = `${dst}.tmp`;

function removeOutputs() {
  try {
    rmSync(dst, { force: true });
    rmSync(tmp, { force: true });
  } catch {
    /* best effort; the exit code below is what the workflow acts on */
  }
}

function fail(message) {
  removeOutputs();
  console.error(`sanitize-results: ${message}`);
  process.exit(1);
}

const verify = (text) => [...new Set([...treeProblems(JSON.parse(text)), ...serializedProblems(text)])];

// Must run BEFORE any deletion: if dst were the source, removing "the stale output" would destroy the input.
if (resolve(src) === resolve(dst) || resolve(src) === resolve(tmp)) {
  console.error("sanitize-results: source and destination are the same file; refusing (nothing touched)");
  process.exit(1);
}

removeOutputs(); // first destructive action: nothing stale can outlive any later failure
process.on("uncaughtException", () => fail("unexpected error; no output written (details withheld)"));

let out;
try {
  const raw = readFileSync(src, "utf8").replace(/^\uFEFF/, "");
  out = JSON.stringify(redactTree(JSON.parse(raw)), null, 2);
} catch (e) {
  // Never print e.message: JSON.parse errors can quote part of the input.
  fail(`could not read or parse ${src}${e && e.code ? ` (${e.code})` : ""}; no output written`);
}

let problems;
try {
  problems = verify(out);
} catch {
  fail("could not verify the sanitized report; no output written");
}
if (problems.length > 0) {
  fail(`REFUSING to write ${dst}; residual sensitive-shaped content: ${problems.join(", ")}`);
}

try {
  writeFileSync(tmp, out);
  renameSync(tmp, dst);
  // Re-read what is actually on disk and verify it once more.
  const onDisk = readFileSync(dst, "utf8");
  if (verify(onDisk).length > 0) fail(`REFUSING to keep ${dst}; post-write verification found sensitive-shaped content`);
} catch {
  fail("could not write the sanitized report; no output left behind");
}
console.log(`sanitize-results: wrote ${dst} (${out.length} bytes) from ${src}`);
