import { expect, test, type Page } from "@playwright/test";

/**
 * Catalog storefront tests. They need the fixture data from e2e/seed_catalog.py
 * (30 published products: 15 hoodies + 15 tees, page size 24, so 2 pages).
 */

const cards = (page: Page) => page.locator('a[href^="/en/products/e2e-"], a[href^="/fa/products/e2e-"]');
const noHorizontalOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test.describe("desktop", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("catalog loads with product cards and count", async ({ page }) => {
    await page.goto("/en/products");
    await expect(page.getByRole("heading", { level: 1, name: "Products" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "30 products" })).toBeVisible();
    await expect(cards(page)).toHaveCount(24);
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  });

  test("search is URL-driven and survives reload", async ({ page }) => {
    await page.goto("/en/products");
    await page.getByRole("searchbox", { name: "Search products" }).fill("Hoodie 07");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page).toHaveURL(/search=Hoodie\+07|search=Hoodie%2007/);
    await expect(page.getByRole("heading", { level: 2, name: "1 products" })).toBeVisible();
    await expect(cards(page)).toHaveCount(1);
    await page.reload();
    await expect(cards(page)).toHaveCount(1);
    await expect(page.getByRole("searchbox", { name: "Search products" })).toHaveValue("Hoodie 07");
  });

  test("category and in-stock filters narrow results via the URL", async ({ page }) => {
    await page.goto("/en/products");
    await page.getByRole("checkbox", { name: "Tees" }).check();
    await page.getByRole("button", { name: "Apply filters" }).click();
    await expect(page).toHaveURL(/category=tees/);
    await expect(page.getByRole("heading", { level: 2, name: "15 products" })).toBeVisible();

    await page.goto("/en/products?category=hoodies");
    await page.getByRole("checkbox", { name: "In stock only" }).check();
    await page.getByRole("button", { name: "Apply filters" }).click();
    await expect(page).toHaveURL(/in_stock=true/);
    await expect(page.getByRole("heading", { level: 2, name: "14 products" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "Hoodies" })).toBeChecked();
  });

  test("price range filter is applied by the backend", async ({ page }) => {
    await page.goto("/en/products?min_price=14000&max_price=15500");
    await expect(page.getByLabel("Minimum price")).toHaveValue("14000");
    await expect(cards(page)).toHaveCount(4); // Tee 14, Tee 15, Hoodie 14 (14500), Hoodie 15 (15500)
  });

  test("sorting is URL-driven", async ({ page }) => {
    await page.goto("/en/products");
    await page.getByRole("link", { name: "Price: low to high" }).click();
    await expect(page).toHaveURL(/sort=price_asc/);
    await expect(cards(page).first().getByRole("heading")).toHaveText("Tee 01");
    await page.getByRole("link", { name: "Price: high to low" }).click();
    await expect(page).toHaveURL(/sort=price_desc/);
    await expect(cards(page).first().getByRole("heading")).toHaveText("Hoodie 15");
    await expect(page.getByRole("link", { name: "Price: high to low" })).toHaveAttribute("aria-current", "true");
  });

  test("pagination uses backend pages and keeps state", async ({ page }) => {
    await page.goto("/en/products?sort=name_asc");
    await expect(page.getByText("Page 1 of 2")).toBeVisible();
    await expect(page.locator('span[aria-disabled="true"]', { hasText: "Previous" })).toBeVisible();
    await page.getByRole("link", { name: "Next" }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(page).toHaveURL(/sort=name_asc/);
    await expect(page.getByText("Page 2 of 2")).toBeVisible();
    await expect(cards(page)).toHaveCount(6);
    await expect(page.locator('span[aria-disabled="true"]', { hasText: "Next" })).toBeVisible();
    await page.goBack();
    await expect(page.getByText("Page 1 of 2")).toBeVisible();
  });

  test("out-of-range page redirects to the first page", async ({ page }) => {
    await page.goto("/en/products?page=99");
    await expect(page).toHaveURL(/\/en\/products$/);
    await expect(cards(page)).toHaveCount(24);
  });

  test("empty search shows an empty state with a way to clear", async ({ page }) => {
    await page.goto("/en/products?search=zzzznothing");
    await expect(page.getByText("No products found")).toBeVisible();
    await page.getByRole("link", { name: "Clear search and filters" }).click();
    await expect(page).toHaveURL(/\/en\/products$/);
    await expect(page.getByRole("heading", { level: 2, name: "30 products" })).toBeVisible();
  });

  test("product detail renders, switches color and honestly disables add to cart", async ({ page }) => {
    await page.goto("/en/products?search=Hoodie%2001");
    await cards(page).first().click();
    await expect(page).toHaveURL(/\/en\/products\/e2e-hoodie-01$/);
    await expect(page.getByRole("heading", { level: 1, name: "Hoodie 01" })).toBeVisible();
    await expect(page.getByText("Fixture Hoodie number 1.")).toBeVisible();
    await expect(page.getByText("In stock", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add to cart" })).toBeDisabled();
    await expect(page.getByText(/cart is not available yet/)).toBeVisible();

    await page.getByRole("link", { name: "White" }).click();
    await expect(page).toHaveURL(/color=white/);
    await expect(page.getByText("Out of stock", { exact: true })).toBeVisible();

    await page.getByRole("link", { name: "Back to products" }).click();
    await expect(page).toHaveURL(/\/en\/products$/);
  });

  test("sale price shows the original struck through, only when the backend has one", async ({ page }) => {
    await page.goto("/en/products/e2e-hoodie-02");
    await expect(page.locator("del")).toContainText("2,500");
    await page.goto("/en/products/e2e-hoodie-04");
    await expect(page.locator("del")).toHaveCount(0);
  });

  test("unknown product is a 404", async ({ page }) => {
    const res = await page.goto("/en/products/does-not-exist");
    expect(res?.status()).toBe(404);
  });
});

test.describe("mobile", () => {
  test.use({ viewport: { width: 375, height: 800 } });

  test("filters open in a dialog, apply and close; no horizontal overflow", async ({ page }) => {
    await page.goto("/en/products");
    expect(await noHorizontalOverflow(page)).toBe(true);
    const dialog = page.getByRole("dialog", { name: "Filters" });
    await expect(dialog).toBeHidden();

    await page.getByRole("button", { name: "Filters" }).click();
    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();

    await page.getByRole("button", { name: "Filters" }).click();
    await dialog.getByRole("checkbox", { name: "Tees" }).check();
    await dialog.getByRole("button", { name: "Apply filters" }).click();
    await expect(page).toHaveURL(/category=tees/);
    await expect(page.getByRole("heading", { level: 2, name: "15 products" })).toBeVisible();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("button", { name: /Filters/ })).toContainText("1");
  });

  test("detail page has no horizontal overflow", async ({ page }) => {
    await page.goto("/en/products/e2e-hoodie-01");
    await expect(page.getByRole("heading", { level: 1, name: "Hoodie 01" })).toBeVisible();
    expect(await noHorizontalOverflow(page)).toBe(true);
  });

  test("Persian page has no horizontal overflow on mobile", async ({ page }) => {
    await page.goto("/fa/products");
    expect(await noHorizontalOverflow(page)).toBe(true);
  });
});

test.describe("localization", () => {
  test("Persian renders RTL with Persian copy and digits", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/fa/products");
    await expect(page.locator("html")).toHaveAttribute("lang", "fa");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { level: 1, name: "محصولات" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "۳۰ محصول" })).toBeVisible();
    await expect(page.getByRole("button", { name: "اعمال فیلترها" })).toBeVisible();
  });

  test("language switch keeps the catalog route", async ({ page }) => {
    await page.goto("/fa/products");
    await page.getByRole("link", { name: /English/ }).first().click();
    await expect(page).toHaveURL(/\/en\/products$/);
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  });
});
