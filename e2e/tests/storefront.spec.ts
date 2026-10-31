import { expect, test } from "@playwright/test";

test("storefront uses Persian RTL and the header contains only the agreed links", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/fa/about");
  await expect(page.locator("html")).toHaveAttribute("lang", "fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  const nav = page.getByRole("navigation", { name: "ناوبری اصلی" });
  for (const name of ["محصولات", "درباره ما", "سوالات متداول", "پشتیبانی"]) {
    await expect(nav.getByRole("link", { name })).toBeVisible();
  }
  for (const removed of ["تماس با ما", "بازگشت کالا", "پروفایل", "سبد خرید"]) {
    await expect(nav.getByRole("link", { name: removed })).toHaveCount(0);
  }
  await expect(page.getByRole("link", { name: "حساب کاربری" })).toBeVisible();
});

test("hero banner uses supplied VZ artwork and is not a link", async ({ page }) => {
  await page.goto("/fa");
  const hero = page.locator("section[aria-label='بنر ویژه ودزمانی']");
  await expect(hero).toBeVisible();
  await expect(hero.locator("img")).toHaveAttribute("src", /vedzmani-banner-vz\.svg/);
  await expect(hero.locator("a")).toHaveCount(0);
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
  await dialog.locator("summary").filter({ hasText: "دسته‌بندی‌ها" }).click();
  const categories = [
    { name: "دورس" },
    { name: "پیراهن" },
    { name: "تی شرت" },
    { name: "هودی" },
    { name: "کاپشن" },
    { name: "جکت", href: "/fa/categories/jackets" },
    { name: "جکت چرم", href: "/fa/categories/leather-jackets" },
    { name: "شلوار جین" },
    { name: "شلوار پارچه ای" },
    { name: "جاگر" },
    { name: "کتونی" },
    { name: "اکسسوری" },
  ];
  for (const category of categories) {
    const link = dialog.getByRole("link", { name: category.name, exact: true });
    await expect(link).toBeVisible();
    if (category.href) await expect(link).toHaveAttribute("href", category.href);
  }
  for (const name of ["محصولات", "درباره ما", "سوالات متداول", "پشتیبانی"]) {
    await expect(dialog.getByRole("link", { name, exact: true })).toBeVisible();
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("cart icon badge stays current when the initial cart request resolves after add-to-cart", async ({ page }) => {
  let releaseInitialGet!: () => void;
  const initialGet = new Promise<void>((resolve) => {
    releaseInitialGet = resolve;
  });
  let initialGetPending = true;

  await page.route("**/api/cart/", async (route) => {
    if (initialGetPending) {
      initialGetPending = false;
      await initialGet;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ item_count: 0 }),
    });
  });
  await page.route("**/api/auth/csrf/", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ csrfToken: "e2e-csrf" }) }),
  );
  await page.route("**/api/cart/items/", (route) =>
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ item_count: 1 }),
    }),
  );

  await page.goto("/fa/products/e2e-hoodie-01");
  const cartUpdated = page.evaluate(
    () => new Promise<void>((resolve) => window.addEventListener("vedzmani:cart-updated", () => resolve(), { once: true })),
  );
  await page.locator("label").filter({ has: page.getByRole("radio", { name: "M" }) }).click();
  await page.getByRole("button", { name: "افزودن به سبد خرید" }).click();
  await cartUpdated;

  // Release the stale initial GET only after the successful mutation event reached the header.
  releaseInitialGet();
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
