import { expect, test } from "@playwright/test";

const noHorizontalOverflow = (page: import("@playwright/test").Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

for (const viewport of [{ name: "دسکتاپ", width: 1280, height: 800 }, { name: "موبایل", width: 375, height: 800 }]) {
  test(`${viewport.name}: Navbar فقط هنگام جست‌وجو بزرگ می‌شود و بعد به حالت اصلی برمی‌گردد`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("/fa");

    const headerBar = page.locator("header > div").first();
    const searchRoot = page.getByTestId("navbar-search-root");
    const beforeHeader = await headerBar.boundingBox();
    const beforeSearch = await searchRoot.boundingBox();
    expect(beforeHeader).not.toBeNull();
    expect(beforeSearch).not.toBeNull();

    await page.getByRole("button", { name: "جستجوی محصولات" }).click();
    const input = page.getByRole("searchbox", { name: "جستجوی نام یا کد محصول" });
    await expect(input).toHaveAttribute("placeholder", "جستجو");
    await input.fill("Hoodie 07");

    const panel = page.getByTestId("navbar-search-panel");
    const result = panel.getByRole("button", { name: /Hoodie 07/ }).first();
    await expect(result).toBeVisible();

    const expandedHeader = await headerBar.boundingBox();
    const expandedSearch = await searchRoot.boundingBox();
    const panelBox = await panel.boundingBox();
    expect(expandedHeader).not.toBeNull();
    expect(expandedSearch).not.toBeNull();
    expect(panelBox).not.toBeNull();
    expect((expandedHeader?.height ?? 0)).toBeGreaterThan((beforeHeader?.height ?? 0));
    if (viewport.width < 768) {
      // On narrow screens the header already spans the viewport in its normal state.
      // Expansion is expressed by height and shape, not impossible extra width.
      expect(expandedHeader?.width).toBeCloseTo(beforeHeader?.width ?? 0, 0);
    } else {
      expect((expandedHeader?.width ?? 0)).toBeGreaterThan((beforeHeader?.width ?? 0));
    }
    expect((expandedSearch?.width ?? 0)).toBeGreaterThan((beforeSearch?.width ?? 0));
    expect(Math.abs((panelBox?.x ?? 0) + (panelBox?.width ?? 0) / 2 - viewport.width / 2)).toBeLessThanOrEqual(2);
    expect(await noHorizontalOverflow(page)).toBe(true);

    await page.keyboard.press("Escape");
    await expect(panel).toBeHidden();
    await expect(headerBar).toHaveClass(/rounded-full/);
    const closedHeader = await headerBar.boundingBox();
    expect(closedHeader?.width).toBeCloseTo(beforeHeader?.width ?? 0, 0);
    expect(await noHorizontalOverflow(page)).toBe(true);
  });
}

test("انتخاب نتیجه، صفحه را عوض می‌کند و Navbar را به حالت عادی برمی‌گرداند", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto("/fa");

  const headerBar = page.locator("header > div").first();
  const before = await headerBar.boundingBox();
  await page.getByRole("button", { name: "جستجوی محصولات" }).click();
  const input = page.getByRole("searchbox", { name: "جستجوی نام یا کد محصول" });
  await input.fill("Hoodie 07");

  const result = page.getByTestId("navbar-search-panel").getByRole("button", { name: /Hoodie 07/ }).first();
  await expect(result).toBeVisible();
  await result.click();
  await expect(page).toHaveURL(/\/fa\/products\/e2e-hoodie-07\?color=black$/);
  await expect(headerBar).toHaveClass(/rounded-full/);
  const after = await headerBar.boundingBox();
  expect(after?.width).toBeCloseTo(before?.width ?? 0, 0);
});
