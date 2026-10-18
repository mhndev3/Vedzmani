// Reads Playwright's JSON report and prints per-status counts plus the purchase-journey result as GitHub
// annotations, so a green job cannot hide a skipped journey test. Exits 1 unless that test actually passed.
import { readFileSync } from "node:fs";

const report = JSON.parse(readFileSync(process.argv[2] ?? "results.json", "utf8"));
const tests = [];
const walk = (suite) => {
  for (const spec of suite.specs ?? []) {
    for (const t of spec.tests) tests.push({ file: spec.file, title: spec.title, status: t.status });
  }
  for (const child of suite.suites ?? []) walk(child);
};
report.suites.forEach(walk);

const counts = {};
for (const t of tests) counts[t.status] = (counts[t.status] ?? 0) + 1;
console.log(`::notice title=Playwright statuses::${tests.length} tests ${JSON.stringify(counts)}`);

const journey = tests.filter((t) => t.file.endsWith("purchase-journey.spec.ts"));
const verdict = journey.map((t) => `${t.status}: ${t.title}`).join(" | ") || "NOT FOUND";
console.log(`::notice title=Purchase journey::${verdict}`);
if (journey.length !== 1 || journey[0].status !== "expected") {
  console.log("::error title=Purchase journey::did not run to a pass (skipped, failed or missing)");
  process.exit(1);
}
