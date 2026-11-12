import { expect, test as base } from "@playwright/test";
import type { Page } from "@playwright/test";

// The app can keep lazy images, fonts, or other resources open after the document
// is usable. UI assertions wait for the elements they need; navigation itself
// should not block on the browser's "load" event.
export const test = base.extend({
  page: async ({ page }, use) => {
    const originalGoto = page.goto.bind(page);
    const originalReload = page.reload.bind(page);
    const originalGoBack = page.goBack.bind(page);
    const originalGoForward = page.goForward.bind(page);

    page.goto = (async (url: string, options?: Parameters<Page["goto"]>[1]) =>
      originalGoto(url, { waitUntil: "domcontentloaded", ...options })) as Page["goto"];
    page.reload = (async (options?: Parameters<Page["reload"]>[0]) =>
      originalReload({ waitUntil: "domcontentloaded", ...options })) as Page["reload"];
    page.goBack = (async (options?: Parameters<Page["goBack"]>[0]) =>
      originalGoBack({ waitUntil: "domcontentloaded", ...options })) as Page["goBack"];
    page.goForward = (async (options?: Parameters<Page["goForward"]>[0]) =>
      originalGoForward({ waitUntil: "domcontentloaded", ...options })) as Page["goForward"];

    await use(page);
  },
});

export { expect };
export type { Page, Route } from "@playwright/test";
