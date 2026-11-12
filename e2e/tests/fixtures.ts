import { expect, test as base } from "@playwright/test";
import type { Page } from "@playwright/test";

// The storefront can keep image/font requests open after the document is usable.
// E2E assertions already wait for the UI they need, so navigation should not wait
// for every external or lazy-loaded resource to emit the browser's "load" event.
export const test = base.extend({
  page: async ({ page }, use) => {
    const originalGoto = page.goto.bind(page);
    page.goto = (async (url: string, options?: Parameters<Page["goto"]>[1]) =>
      originalGoto(url, { waitUntil: "domcontentloaded", ...options })) as Page["goto"];
    await use(page);
  },
});

export { expect };
export type { Page, Route } from "@playwright/test";
