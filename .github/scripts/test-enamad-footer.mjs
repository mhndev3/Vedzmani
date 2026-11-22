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
  /<section\\s+aria-label=\\{locale === "fa" \\? "نماد اعتماد الکترونیکی" : "Electronic trust seal"\\}\\s+className="([^"]+)"[\\s\\S]*?<EnamadSeal\\s*\\/>/,
);
assert.ok(sealSection, "The official Enamad seal section must exist");
assert.match(sealSection[1], /(?:^|\\s)shrink-0(?:\\s|$)/, "The seal must not shrink on the shared mobile row");

assert.match(seal, /referrerPolicy="origin"/, "The official referrer policy must be preserved");
assert.match(seal, /target="\\_blank"/, "The official seal must open its verification page in a new tab");
assert.match(seal, /href=\\{ENAMAD_LINK_URL\\}/, "The seal must link to the official verification page");
assert.match(seal, /trustseal\\.enamad\\.ir\\/\\?id=8480737&Code=/, "The official verification URL must remain intact");
assert.match(seal, /trustseal\\.enamad\\.ir\\/logo\\.aspx\\?id=8480737&Code=/, "The official image URL must remain intact");
assert.match(seal, /code=\\{ENAMAD_CODE\\}/, "The official Enamad code attribute must be preserved");
assert.match(seal, /alt=""/, "The image alt text must match the official embed snippet");
assert.doesNotMatch(seal, /loading=|fetchPriority=|decoding=|onError=|retry=/, "The official embed must not add image-loading or retry modifications");

console.log("Official Enamad embed markup and unchanged footer layout contract passed");
