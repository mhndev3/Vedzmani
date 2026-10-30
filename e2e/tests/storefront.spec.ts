import { expect, test } from "@playwright/test";

test("storefront uses Persian RTL and the header contains only the agreed links", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/fa/about");
  await expect(page.locator("html")).toHaveAttribute("lang", "fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  const nav = page.getByRole("navigation", { name: "ناوبری اصلی" });
  for (const name of ["همه محصولات", "درباره ما", "سوالات متداول", "پشتیبانی"]) {
    await expect(nav.getByRole("link", { name })).toBeVisible();
  }
  for (const removed of ["تماس با ما", "بازگشت کالا", "پروفایل", "سبد خرید"]) {
    await expect(nav.getByRole("link", { name: removed })).toHaveCount(0);
  }
});

test("theme toggle switches dark mode and persists", async ({ page }) => {
  await page.goto("/fa");
  const html = page.locator("html");
  await page.getByRole("button", { name: "حالت تیره" }).click();
  await expect(html).toHaveClass(/dark/);
  await page.reload();
  await expect(html).toHaveClass(/dark/);
});

test("hamburger menu contains the requested categories and support links", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/fa");
  await page.getByRole("button", { name: "باز کردن منو" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  for (const category of ["دورس", "پیراهن", "تی شرت", "هودی", "کاپشن", "جکت", "شلوار جین", "شلوار پارچه ای", "جاگر", "کتونی", "اکسسوری"]) {
    await expect(dialog.getByRole("link", { name: category })).toBeVisible();
  }
  for (const name of ["همه محصولات", "درباره ما", "سوالات متداول", "پشتیبانی"]) {
    await expect(dialog.getByRole("link", { name })).toBeVisible();
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("cart icon badge updates immediately after a successful add-to-cart response", async ({ page }) => {
  await page.route("**/api/cart/", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ item_count: 0 }) }),
  );
  await page.route("**/api/auth/csrf/", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ csrfToken: "e2e-csrf" }) }),
  );
  await page.route("**/api/cart/items/", (route) =>
    route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ item_count: 1 }) }),
  );

  await page.goto("/fa/products/e2e-hoodie-01");
  await page.locator("label").filter({ has: page.getByRole("radio", { name: "M" }) }).click();
  await page.getByRole("button", { name: "افزودن به سبد خرید" }).click();
  await expect(page.getByRole("link", { name: "سبد خرید، ۱ کالا" })).toBeVisible();
});

test("header hides while scrolling and returns after scrolling stops", async ({ page }) => {
  await page.goto("/fa/products");
  const menuButton = page.getByRole("button", { name: "باز کردن منو" });
  await menuButton.click();
  await page.keyboard.press("Escape");
  const header = page.locator("header").first();
  await page.evaluate(() => window.dispatchEvent(new Event("scroll")));
  await expect(header).toHaveAttribute("aria-hidden", "true");
  await expect(header).toHaveAttribute("aria-hidden", "false", { timeout: 1500 });
});

test("header search opens and blank search does not show products", async ({ page }) => {
  await page.goto("/fa");
  await page.getByRole("button", { name: "جستجوی محصولات" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("list")).toHaveCount(0);
  await expect(dialog.getByText("جستجوهای اخیر")).toHaveCount(0);
});
