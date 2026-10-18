// Reads Playwright's JSON report (the real schema: suites -> nested suites -> specs -> tests, where each
// test has an aggregated `status` of expected | unexpected | flaky | skipped and a list of per-retry
// `results`) and prints GitHub annotations. Exit code 1 means the run must not be treated as a success:
//   - any test failed (unexpected) or was skipped, or the report cannot be parsed or is inconsistent;
//   - the purchase journey, or the checkout spec, is missing or is not fully passing.
// A flaky test (failed, then passed on retry) is reported as a warning, except for the purchase journey.
import { readFileSync } from "node:fs";

const fail = (message) => {
  console.log(`::error title=E2E report::${message}`);
  process.exitCode = 1;
};

let report;
try {
  report = JSON.parse(readFileSync(process.argv[2] ?? "results.json", "utf8"));
} catch (error) {
  fail(`cannot read the Playwright JSON report: ${error.message}`);
  process.exit(1);
}

const tests = [];
const walk = (suite) => {
  for (const spec of suite.specs ?? []) {
    for (const test of spec.tests ?? []) {
      tests.push({ file: spec.file, title: spec.title, status: test.status, attempts: (test.results ?? []).length });
    }
  }
  for (const child of suite.suites ?? []) walk(child);
};
(report.suites ?? []).forEach(walk);

const counts = { expected: 0, unexpected: 0, flaky: 0, skipped: 0 };
for (const t of tests) counts[t.status] = (counts[t.status] ?? 0) + 1;
const executed = tests.length - counts.skipped;
console.log(
  `::notice title=Playwright counts::discovered ${tests.length}, executed ${executed}, passed ${counts.expected}, ` +
    `failed ${counts.unexpected}, flaky ${counts.flaky}, skipped ${counts.skipped}`,
);

// The parser must see exactly what Playwright itself counted.
const s = report.stats;
if (!s || s.expected + s.unexpected + s.flaky + s.skipped !== tests.length || s.skipped !== counts.skipped || s.unexpected !== counts.unexpected) {
  fail(`parsed ${tests.length} tests but report.stats says ${JSON.stringify(s)}`);
}

for (const t of tests.filter((x) => x.status === "unexpected")) fail(`FAILED: ${t.file}: ${t.title}`);
for (const t of tests.filter((x) => x.status === "skipped")) fail(`SKIPPED (every spec must run in CI): ${t.file}: ${t.title}`);
for (const t of tests.filter((x) => x.status === "flaky")) {
  console.log(`::warning title=Flaky test::${t.file}: ${t.title} passed only after a retry`);
}

// Specs that must be present and passing. The purchase journey consumes stock and creates an order, so a retry
// is not a clean pass: it must pass on the first attempt. Other required specs may pass on a retry (warned above).
const required = [
  { suffix: "purchase-journey.spec.ts", exactly: 1, firstTry: true },
  { suffix: "checkout.spec.ts", atLeast: 1, firstTry: false },
];
for (const { suffix, exactly, atLeast, firstTry } of required) {
  const found = tests.filter((t) => t.file.endsWith(suffix));
  const ok = found.filter((t) => t.status === "expected" || (!firstTry && t.status === "flaky")).length;
  console.log(`::notice title=${suffix}::${found.length ? `${ok}/${found.length} passed` : "NOT FOUND"}`);
  if ((exactly !== undefined && found.length !== exactly) || (atLeast !== undefined && found.length < atLeast)) {
    fail(`${suffix}: expected ${exactly ?? `at least ${atLeast}`} test(s), found ${found.length}`);
  } else if (ok !== found.length) {
    fail(`${suffix}: ${found.length - ok} test(s) did not pass${firstTry ? " first time" : ""}`);
  }
}
