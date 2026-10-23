import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Product detail: which backend id a size sends, unavailable sizes/colors, failure states and the
 * localized 404. Needs the fixtures from e2e/seed_catalog.py:
 *   - e2e-tee-15: black has exactly one sold-out size (L); white is fully in stock
 *   - e2e-hoodie-01: white is sold out entirely
 *   - e2e-hoodie-02: both colors in stock
 * Tests marked "(mocked response)" intercept the browser's cart request; every other test talks to
 * the real backend. Server-side rendering failures (Django down while Next renders) cannot be
 * produced from the browser, so they are not covered here.
 */

type Detail = {
  colors: { slug: string; sizes: { id: number; label: string; in_stock: boolean }[] }[];
};

async function backendSizeId(
  request: APIRequestContext,
  slug: string,
  color: string,
  label: string,
): Promise<number> {
  const res = await request.get(`/api/catalog/products/${slug}/`);
  expect(res.ok()).toBe(true);
  const product = (await res.json()) as Detail;
  const size = product.colors.find((c) => c.slug === color)?.sizes.find((s) => s.label === label);
  if (!size) throw new Error(`fixture missing: ${slug} ${color} ${label}`);
  return size.id;
}

const isCartAdd = (r: { url(): string; method(): string }) =>
  r.url().endsWith("/api/cart/items/") && r.method() === "POST";

async function selectSize(page: Page, label: string) {
  await page.getByRole("radio", { name: label, exact: true }).check({ force: true });
}

test.describe("variant selection", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("add to cart sends the backend id of the selected size", async ({ page, request }) => {
    const expected = await backendSizeId(request, "e2e-tee-15", "black", "M");
    await page.goto("/en/products/e2e-tee-15");
    await selectSize(page, "M");

    const posted = page.waitForRequest(isCartAdd);
    await page.getByRole("button", { name: "Add to cart" }).click();
    expect((await posted).postDataJSON()).toEqual({ variant_size_id: expected, quantity: 1 });

    // Anonymous visitor: Django answers 401, so the page offers sign-in and never claims success.
    await expect(page.getByRole("alert").filter({ hasText: "Sign in to use your cart." })).toBeVisible();
    await expect(page.getByText("Added to your cart.")).toHaveCount(0);
  });

  test("another color sends that color's own size id", async ({ page, request }) => {
    const black = await backendSizeId(request, "e2e-hoodie-02", "black", "M");
    const white = await backendSizeId(request, "e2e-hoodie-02", "white", "M");
    expect(white).not.toBe(black);

    await page.goto("/en/products/e2e-hoodie-02?color=white");
    await selectSize(page, "M");
    const posted = page.waitForRequest(isCartAdd);
    await page.getByRole("button", { name: "Add to cart" }).click();
    expect((await posted).postDataJSON()).toEqual({ variant_size_id: white, quantity: 1 });
  });

  test("a sold-out size of an in-stock color cannot be selected or sent", async ({ page }) => {
    let cartRequests = 0;
    page.on("request", (r) => {
      if (isCartAdd(r)) cartRequests += 1;
    });
    await page.goto("/en/products/e2e-tee-15");

    await expect(page.getByText("In stock", { exact: true })).toBeVisible();
    await expect(page.getByRole("radio", { name: "S", exact: true })).toBeEnabled();
    await expect(page.getByRole("radio", { name: "M", exact: true })).toBeEnabled();
    const sold = page.getByRole("radio", { name: /^L/ });
    await expect(sold).toBeDisabled();
    await expect(sold).not.toBeChecked();
    await expect(sold).toHaveAccessibleName(/Out of stock/);

    // Nothing selected: the form refuses locally and sends nothing.
    await page.getByRole("button", { name: "Add to cart" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Choose a size before adding to your cart." })).toBeVisible();
    expect(cartRequests).toBe(0);
  });

  test("a fully sold-out color is marked in the color list", async ({ page }) => {
    await page.goto("/en/products/e2e-hoodie-01");
    await expect(page.getByRole("link", { name: /White.*\(Out of stock\)/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Black/ })).not.toContainText("Out of stock");
  });
});

test.describe("add to cart failures", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("a network failure is reported, never shown as success, and can be retried", async ({ page }) => {
    await page.route("**/api/cart/items/", (route) => route.abort("failed"));
    await page.goto("/en/products/e2e-tee-15");
    await selectSize(page, "M");
    await page.getByRole("button", { name: "Add to cart" }).click();

    await expect(
      page.getByRole("alert").filter({ hasText: "Could not reach the store. Check your connection and try again." }),
    ).toBeVisible();
    await expect(page.getByText("Added to your cart.")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Add to cart" })).toBeEnabled();
  });

  test("a stock conflict from Django is shown, not success (mocked response)", async ({ page }) => {
    await page.route("**/api/cart/items/", (route) =>
      route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "insufficient_stock" } }),
      }),
    );
    await page.goto("/en/products/e2e-tee-15");
    await selectSize(page, "M");
    await page.getByRole("button", { name: "Add to cart" }).click();

    await expect(
      page.getByRole("alert").filter({ hasText: "There is not enough stock for that quantity." }),
    ).toBeVisible();
    await expect(page.getByText("Added to your cart.")).toHaveCount(0);
  });
});

test.describe("missing product", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  for (const { locale, dir, title, back } of [
    { locale: "en", dir: "ltr", title: "Product not found", back: "Back to products" },
    { locale: "fa", dir: "rtl", title: "محصول پیدا نشد", back: "بازگشت به محصولات" },
  ]) {
    test(`${locale}: unknown product is a localized 404 with a way back`, async ({ page }) => {
      const res = await page.goto(`/${locale}/products/does-not-exist`);
      expect(res?.status()).toBe(404);
      await expect(page.locator("html")).toHaveAttribute("dir", dir);
      await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
      const link = page.getByRole("link", { name: back });
      await expect(link).toHaveAttribute("href", `/${locale}/products`);
      await link.click();
      await expect(page).toHaveURL(new RegExp(`/${locale}/products$`));
    });
  }
});
