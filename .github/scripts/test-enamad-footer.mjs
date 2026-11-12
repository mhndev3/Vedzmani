import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const footerPath = new URL("../../frontend/src/components/storefront/Footer.tsx", import.meta.url);
const layoutPath = new URL("../../frontend/src/app/[locale]/layout.tsx", import.meta.url);
const footer = readFileSync(footerPath, "utf8");
const layout = readFileSync(layoutPath, "utf8");

assert.match(
  footer,
  /<div dir="rtl" className="[^"]*flex-col[^"]*sm:flex-row[^"]*">/,
  "The footer seal row must stay RTL and stack on mobile",
);

const sealSection = footer.match(
  /<section\s+aria-label=\{locale === "fa" \? "نماد اعتماد الکترونیکی" : "Electronic trust seal"\}\s+className="([^"]+)"[\s\S]*?dangerouslySetInnerHTML/,
);
assert.ok(sealSection, "The official Enamad seal section must exist");
assert.match(sealSection[1], /(?:^|\s)self-end(?:\s|$)/, "On mobile, the seal must align to the left in the RTL column");
assert.match(sealSection[1], /(?:^|\s)sm:self-auto(?:\s|$)/, "Desktop alignment must remain unchanged");
assert.match(footer, /trustseal\.enamad\.ir\/logo\.aspx\?id=8480737/, "The official Enamad image embed must remain intact");
assert.match(footer, /loading="eager"/, "The seal image must not be lazy-loaded");
assert.match(footer, /fetchpriority="high"/, "The seal image must have high fetch priority");
assert.match(footer, /width="120" height="120"/, "The seal image dimensions must be reserved to avoid layout shift");

assert.match(layout, /<link rel="preconnect" href="https:\/\/trustseal\.enamad\.ir"\s*\/>/, "The browser must preconnect to Enamad before rendering the footer");
assert.match(layout, /<link rel="preload" as="image" href=\{enamadImageUrl\} fetchPriority="high"\s*\/>/, "The official seal image must preload with high priority");
assert.match(layout, /const enamadImageUrl = "https:\/\/trustseal\.enamad\.ir\/logo\.aspx\?id=8480737&Code=/, "Preload must target the exact official seal image");

console.log("Enamad first-load performance and responsive alignment contract passed");
