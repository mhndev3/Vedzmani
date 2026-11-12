import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const footerPath = new URL("../../frontend/src/components/storefront/Footer.tsx", import.meta.url);
const sealPath = new URL("../../frontend/src/components/storefront/EnamadSeal.tsx", import.meta.url);
const footer = readFileSync(footerPath, "utf8");
const seal = readFileSync(sealPath, "utf8");

assert.match(
  footer,
  /<div dir="rtl" className="[^"]*flex-col[^"]*sm:flex-row[^"]*">/,
  "The footer seal row must stay RTL and stack on mobile",
);

const sealSection = footer.match(
  /<section\s+aria-label=\{locale === "fa" \? "نماد اعتماد الکترونیکی" : "Electronic trust seal"\}\s+className="([^"]+)"[\s\S]*?<EnamadSeal\s*\/>/,
);
assert.ok(sealSection, "The official Enamad seal section must exist");
assert.match(sealSection[1], /(?:^|\s)self-end(?:\s|$)/, "On mobile, the seal must align to the left in the RTL column");
assert.match(sealSection[1], /(?:^|\s)sm:self-auto(?:\s|$)/, "Desktop alignment must remain unchanged");
assert.match(seal, /trustseal\.enamad\.ir\/logo\.aspx\?id=8480737/, "The official Enamad image URL must remain intact");
assert.match(seal, /MAX_RETRIES\s*=\s*3/, "Enamad image retries must remain bounded");
assert.match(seal, /INITIAL_LOAD_TIMEOUT_MS\s*=\s*8000/, "A slow initial Enamad image load must be retried");
assert.match(seal, /onError=\{\(\)\s*=>/, "A failed Enamad image request must trigger a retry");

console.log("Enamad footer responsive alignment and first-load recovery contract passed");
