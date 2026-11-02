import { expect, test } from "@playwright/test";

const noHorizontalOverflow = (page: import("@playwright/test").Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test.describe("جست‌وجوی واکنش‌گرای Navbar", () => {
  test("در دسکتاپ باز شدن فیلد اجزای هدر را جابه‌جا نمی‌کند و پنل وسط است", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/fa");

    const root = page.getByTestId("navbar-search-root");
    const profile = page.locator('a[href="/fa/profile"]');
    const beforeRoot = await root.boundingBox();
    const beforeProfile = await profile.boundingBox();
    expect(beforeRoot).not.toBeNull();
    expect(beforeProfile).not.toBeNull();

    await page.getByRole("button", { name: "جستجوی محصولات" }).click();
    const input = page.getByRole("searchbox", { name: "جستجوی نام یا کد محصول" });
    await expect(input).toHaveAttribute("placeholder", "جستجو");
    await input.fill("Hoodie 07");

    const panel = page.getByTestId("navbar-search-panel");
    await expect(panel.getByRole("button", { name: /Hoodie 07/ })).toBeVisible();

    const afterRoot = await root.boundingBox();
    const afterProfile = await profile.boundingBox();
    const panelBox = await panel.boundingBox();
    expect(afterRoot).not.toBeNull();
    expect(afterProfile).not.toBeNull();
    expect(panelBox).not.toBeNull();
    expect(Math.abs((afterRoot?.width ?? 0) - (beforeRoot?.width ?? 0))).toBeLessThanOrEqual(1);
    expect(Math.abs((afterProfile?.x ?? 0) - (beforeProfile?.x ?? 0))).toBeLessThanOrEqual(1);
    expect(Math.abs((panelBox?.x ?? 0) + (panelBox?.width ?? 0) / 2 - 640)).toBeLessThanOrEqual(2);
    expect(await noHorizontalOverflow(page)).toBe(true);
  });

  test("در موبایل Navbar ثابت می‌ماند و پنل نتایج دقیقاً وسط صفحه است", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto("/fa");

    const root = page.getByTestId("navbar-search-root");
    const profile = page.locator('a[href="/fa/profile"]');
    const beforeRoot = await root.boundingBox();
    const beforeProfile = await profile.boundingBox();
    expect(beforeRoot).not.toBeNull();
    expect(beforeProfile).not.toBeNull();

    await page.getByRole("button", { name: "جستجوی محصولات" }).click();
    const input = page.getByRole("searchbox", { name: "جستجوی نام یا کد محصول" });
    await expect(input).toHaveAttribute("placeholder", "جستجو");
    await input.fill("Hoodie 07");

    const panel = page.getByTestId("navbar-search-panel");
    await expect(panel.getByRole("button", { name: /Hoodie 07/ })).toBeVisible();

    const afterRoot = await root.boundingBox();
    const afterProfile = await profile.boundingBox();
    const panelBox = await panel.boundingBox();
    expect(afterRoot).not.toBeNull();
    expect(afterProfile).not.toBeNull();
    expect(panelBox).not.toBeNull();
    expect(Math.abs((afterRoot?.width ?? 0) - (beforeRoot?.width ?? 0))).toBeLessThanOrEqual(1);
    expect(Math.abs((afterProfile?.x ?? 0) - (beforeProfile?.x ?? 0))).toBeLessThanOrEqual(1);
    expect(Math.abs((panelBox?.x ?? 0) + (panelBox?.width ?? 0) / 2 - 187.5)).toBeLessThanOrEqual(2);
    expect(await noHorizontalOverflow(page)).toBe(true);
  });
});
