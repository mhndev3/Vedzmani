import { expect, test, type Page } from "@playwright/test";

/**
 * Cart page UI behavior (frontend/src/components/storefront/cart/CartView.tsx).
 *
 * Every /api/cart/ and /api/auth/csrf/ response here is MOCKED with page.route, so these tests need
 * only a running frontend (E2E_BASE_URL, default http://localhost:8080) and NO backend, database or
 * session. They assert what the page does with a given server answer and which requests it sends.
 * They do not prove Django's behavior: that is covered by backend/tests/test_cart_api.py and, with
 * the real API, by purchase-journey.spec.ts and checkout.spec.ts.
 *
 * The mocked "server" deliberately returns totals that are NOT quantity x unit price, so a page that
 * computed totals in the browser would fail these tests.
 */

type Call = { method: string; path: string; body: unknown; csrf: string | undefined };
type Reply = { status?: number; json: unknown } | "abort";

const line = (id: number, quantity: number, over: Record<string, unknown> = {}) => ({
  id,
  quantity,
  availability: "available",
  unit_price: "1000",
  subtotal: String(1000 * quantity),
  product: { id: 1, name: "Linen Shirt", slug: "linen-shirt" },
  color: { name: "Black", slug: "black", hex_color: "#000000" },
  variant_size: { id: 10 + id, sku: `SKU-${id}`, size: "M", label: "M" },
  image: null,
  ...over,
});

const cartOf = (items: ReturnType<typeof line>[], total: string, hasIssues = false) => ({
  items,
  item_count: items.length,
  total_quantity: items.reduce((n, i) => n + i.quantity, 0),
  total,
  has_issues: hasIssues,
});

const EMPTY = cartOf([], "0");
const err = (status: number, code: string) => ({ status, json: { error: { code, message: code } } }) as Reply;

/** Mocks the CSRF endpoint and every /api/cart/ call; returns the recorded calls. */
async function mockApi(page: Page, respond: (call: Call, calls: Call[]) => Reply | Promise<Reply>) {
  const calls: Call[] = [];
  await page.route("**/api/auth/csrf/", (r) => r.fulfill({ json: { csrfToken: "test-token" } }));
  await page.route(/\/api\/cart\//, async (route) => {
    const req = route.request();
    const call: Call = {
      method: req.method(),
      path: new URL(req.url()).pathname,
      body: req.postDataJSON(),
      csrf: req.headers()["x-csrftoken"],
    };
    calls.push(call);
    const reply = await respond(call, calls);
    if (reply === "abort") return route.abort("failed");
    return route.fulfill({ status: reply.status ?? 200, json: reply.json });
  });
  return calls;
}

const gets = (calls: Call[]) => calls.filter((c) => c.method === "GET").length;
const mutations = (calls: Call[]) => calls.filter((c) => c.method !== "GET");
// Next's empty route announcer is also role=alert, so match only an alert that has text.
const alert = (page: Page) => page.getByRole("alert").filter({ hasText: /\S/ });
const updatedNotice = (page: Page) => page.getByText("Cart updated.");
const increase = (page: Page) => page.getByRole("button", { name: "Increase quantity of Linen Shirt" });

test.describe("cart page (mocked API)", () => {
  test("anonymous visitor is asked to sign in and sees no cart controls", async ({ page }) => {
    await mockApi(page, () => err(401, "not_authenticated"));
    await page.goto("/en/cart");
    await expect(page.getByRole("heading", { name: "Sign in to view your cart" })).toBeVisible();
    await expect(page.locator('a[href*="/en/sign-in"]')).toBeVisible();
    await expect(page.getByTestId("cart-line")).toHaveCount(0);
  });

  test("empty cart shows the empty state with a localized browse link", async ({ page }) => {
    await mockApi(page, () => ({ json: EMPTY }));
    await page.goto("/en/cart");
    await expect(page.getByRole("heading", { name: "Your cart is empty" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Browse products" })).toHaveAttribute("href", "/en/products");
    await expect(page.getByText("Proceed to checkout")).toHaveCount(0);
  });

  test("a network failure while loading shows an error and Try again recovers", async ({ page }) => {
    let first = true;
    await mockApi(page, () => {
      if (first) {
        first = false;
        return "abort";
      }
      return { json: cartOf([line(1, 2)], "2000") };
    });
    await page.goto("/en/cart");
    await expect(page.getByRole("heading", { name: "Your cart could not be loaded" })).toBeVisible();
    await expect(page.getByTestId("cart-line")).toHaveCount(0);
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByTestId("cart-line")).toHaveCount(1);
  });

  test("shows product, color, size, quantity, unit price, subtotal and the server total", async ({ page }) => {
    await mockApi(page, () => ({ json: cartOf([line(1, 2, { subtotal: "1999" })], "1999") }));
    await page.goto("/en/cart");
    const row = page.getByTestId("cart-line");
    await expect(row.getByRole("link", { name: "Linen Shirt" })).toHaveAttribute(
      "href",
      "/en/products/linen-shirt?color=black",
    );
    await expect(row).toContainText("Color: Black");
    await expect(row).toContainText("Size: M");
    await expect(row).toContainText("Unit price: 1,000");
    await expect(row.getByTestId("cart-quantity")).toHaveText("2");
    // 1,999 is what the server said; 2 x 1,000 would be 2,000.
    await expect(row.getByLabel("Subtotal")).toHaveText("1,999");
    await expect(page.getByTestId("cart-total")).toHaveText("1,999");
    await expect(page.getByRole("link", { name: "Proceed to checkout" })).toHaveAttribute("href", "/en/checkout");
  });

  test("changing the quantity sends PATCH with CSRF and renders the server's response", async ({ page }) => {
    const calls = await mockApi(page, (c) =>
      c.method === "PATCH"
        ? { json: cartOf([line(1, 3, { subtotal: "4000" })], "4321") }
        : { json: cartOf([line(1, 2)], "2000") },
    );
    await page.goto("/en/cart");
    await increase(page).click();
    await expect(page.getByTestId("cart-quantity")).toHaveText("3");
    await expect(page.getByTestId("cart-total")).toHaveText("4,321");
    await expect(updatedNotice(page)).toHaveCount(1);
    const [patch] = mutations(calls);
    expect(patch).toMatchObject({ method: "PATCH", path: "/api/cart/items/1/", body: { quantity: 3 }, csrf: "test-token" });
  });

  test("removing a line sends DELETE, shows the server's empty cart and moves focus to the heading", async ({ page }) => {
    const calls = await mockApi(page, (c) =>
      c.method === "DELETE" ? { json: EMPTY } : { json: cartOf([line(1, 1)], "1000") },
    );
    await page.goto("/en/cart");
    await page.getByRole("button", { name: "Remove Linen Shirt from cart" }).click();
    await expect(page.getByRole("heading", { name: "Your cart is empty" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
    expect(mutations(calls)).toMatchObject([{ method: "DELETE", path: "/api/cart/items/1/", csrf: "test-token" }]);
  });

  test("a stock conflict (409) is shown as an error, never as success, and the cart is refreshed", async ({ page }) => {
    const calls = await mockApi(page, (c, all) => {
      if (c.method === "PATCH") return err(409, "insufficient_stock");
      // The refresh after the conflict returns the server's current truth.
      return all.length > 1
        ? { json: cartOf([line(1, 2, { availability: "insufficient_stock" })], "0", true) }
        : { json: cartOf([line(1, 2)], "2000") };
    });
    await page.goto("/en/cart");
    await increase(page).click();
    await expect(alert(page)).toHaveText("There is not enough stock for that quantity.");
    await expect(page.getByText(/Not enough stock for this quantity/)).toBeVisible();
    await expect(page.getByTestId("cart-quantity")).toHaveText("2");
    await expect(updatedNotice(page)).toHaveCount(0);
    expect(gets(calls)).toBe(2);
    await expect(page.getByTestId("cart-checkout-blocked")).toBeVisible();
  });

  test("a network failure on a change shows an error and re-reads the cart (outcome unknown)", async ({ page }) => {
    const calls = await mockApi(page, (c) =>
      c.method === "PATCH" ? "abort" : { json: cartOf([line(1, 2)], "2000") },
    );
    await page.goto("/en/cart");
    await increase(page).click();
    await expect(alert(page)).toHaveText("Could not reach the store. Check your connection and try again.");
    await expect(updatedNotice(page)).toHaveCount(0);
    await expect(page.getByTestId("cart-quantity")).toHaveText("2");
    expect(gets(calls)).toBe(2);
  });

  test("a 404 (line removed elsewhere) explains it and refreshes to the server's cart", async ({ page }) => {
    const calls = await mockApi(page, (c, all) => {
      if (c.method === "PATCH") return err(404, "not_found");
      return all.length > 1 ? { json: EMPTY } : { json: cartOf([line(1, 2)], "2000") };
    });
    await page.goto("/en/cart");
    await increase(page).click();
    await expect(alert(page)).toHaveText("That item is no longer in your cart.");
    await expect(page.getByRole("heading", { name: "Your cart is empty" })).toBeVisible();
    expect(gets(calls)).toBe(2);
  });

  test("being signed out during a change returns to the sign-in state", async ({ page }) => {
    await mockApi(page, (c) =>
      c.method === "PATCH" ? err(401, "not_authenticated") : { json: cartOf([line(1, 2)], "2000") },
    );
    await page.goto("/en/cart");
    await increase(page).click();
    await expect(page.getByRole("heading", { name: "Sign in to view your cart" })).toBeVisible();
    await expect(page.getByTestId("cart-line")).toHaveCount(0);
  });

  test("when the cart cannot proceed, checkout is blocked, focusable and explained", async ({ page }) => {
    await mockApi(page, () => ({
      json: cartOf([line(1, 1), line(2, 1, { availability: "unavailable", subtotal: "1000" })], "1000", true),
    }));
    await page.goto("/en/cart");
    await expect(page.getByRole("link", { name: "Proceed to checkout" })).toHaveCount(0);
    const blocked = page.getByTestId("cart-checkout-blocked");
    await expect(blocked).toHaveAttribute("aria-disabled", "true");
    const noteId = await blocked.getAttribute("aria-describedby");
    await expect(page.locator(`#${noteId}`)).toHaveText("Some items need your attention before you can check out.");
    await blocked.focus();
    await expect(blocked).toBeFocused();
    // force: Playwright treats aria-disabled as not actionable, but a real user can still click it.
    await blocked.click({ force: true });
    await expect(page).toHaveURL(/\/en\/cart$/);
    // An unavailable line can only be removed, not edited.
    const rows = page.getByTestId("cart-line");
    await expect(rows.nth(1).getByRole("button", { name: /Increase quantity/ })).toBeDisabled();
    await expect(rows.nth(1).getByRole("button", { name: /Remove .* from cart/ })).toBeEnabled();
  });

  test("a double click sends exactly one change request", async ({ page }) => {
    const calls = await mockApi(page, async (c) => {
      if (c.method !== "PATCH") return { json: cartOf([line(1, 2)], "2000") };
      await new Promise((resolve) => setTimeout(resolve, 400));
      return { json: cartOf([line(1, 3)], "3000") };
    });
    await page.goto("/en/cart");
    await increase(page).dblclick();
    await expect(page.getByTestId("cart-quantity")).toHaveText("3");
    expect(mutations(calls)).toHaveLength(1);
  });

  test("Persian locale renders RTL with localized routes", async ({ page }) => {
    await mockApi(page, () => ({ json: cartOf([line(1, 1)], "1000") }));
    await page.goto("/fa/cart");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { level: 1, name: "سبد خرید" })).toBeVisible();
    await expect(page.locator('a[href="/fa/checkout"]')).toBeVisible();
    await expect(page.locator('a[href="/fa/products/linen-shirt?color=black"]')).toBeVisible();
  });
});
