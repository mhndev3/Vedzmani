import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const footerPath = new URL("../../frontend/src/components/storefront/Footer.tsx", import.meta.url);
const sealPath = new URL("../../frontend/src/components/storefront/EnamadSeal.tsx", import.meta.url);
const footer = readFileSync(footerPath, "utf8");
const seal = readFileSync(sealPath, "utf8");

assert.match(
  footer,
  /<div dir="rtl" className="[^"]*flex-row[^"]*items-center[^"]*justify-between[^"]*">/,
  "The Instagram logo and Enamad seal must stay on one RTL row on mobile",
);

const sealSection = footer.match(
  /<section\s+aria-label=\{locale === "fa" \? "نماد اعتماد الکترونیکی" : "Electronic trust seal"\}\s+className="([^"]+)"[\s\S]*?<EnamadSeal\s*\/>/,
);
assert.ok(sealSection, "The official Enamad seal section must exist");
assert.match(sealSection[1], /(?:^|\s)shrink-0(?:\s|$)/, "The seal must not shrink on the shared mobile row");
assert.match(seal, /trustseal\.enamad\.ir\/logo\.aspx\?id=8480737/, "The official Enamad image URL must remain intact");
assert.match(seal, /MAX_RETRIES\s*=\s*3/, "Enamad image retries must remain bounded");
assert.doesNotMatch(
  seal,
  /INITIAL_LOAD_TIMEOUT_MS/,
  "A slow image must not trigger unconditional duplicate requests",
);
assert.match(seal, /loading="lazy"/, "The Enamad image must not compete with critical initial resources");
assert.match(seal, /fetchPriority="low"/, "The Enamad image must remain low priority");
assert.match(seal, /onError=\{\(\)\s*=>/, "A failed Enamad image request must trigger a retry");

console.log("Enamad footer responsive alignment and non-blocking image recovery contract passed");
