import { expect, test } from "@playwright/test";
import { execSync } from "node:child_process";

/**
 * Purchase journey smoke test, driven entirely through the UI:
 *   storefront -> product -> size -> add to cart -> cart -> OTP sign-in -> checkout -> order confirmation.
 *
 * STATUS: UNVERIFIED. Written in an environment where package registries were unreachable, so this
 * file has not been executed. Run it (see e2e/README-purchase-journey.md) before trusting it.
 *
 * Sign-in uses the real OTP UI. The code is read from the TEST backend's log, which only works because
 * config.settings.dev uses the DEV-ONLY ConsoleDelivery. That is not SMS delivery. Needs a THROWAWAY
 * stack seeded with e2e/seed_catalog.py. Never point E2E_OTP_LOG_COMMAND at a stack with real customers.
 *
 *   E2E_OTP_LOG_COMMAND  shell command printing the test backend log (same as signin.spec.ts)
 *
 * Fixture used: e2e-hoodie-10 / black / size M (stock 5), not touched by the other specs.
 * Single-use: it consumes one unit of stock, so re-seed a fresh database before a second run.
 */

const otpLogCommand = process.env.E2E_OTP_LOG_COMMAND;
const PRODUCT = "e2e-hoodie-10";
const money = (value: string) => new Intl.NumberFormat("en-US").format(Number(value));

async function readOtp(canonicalPhone: string): Promise<string> {
  const re = new RegExp(`phone=\\${canonicalPhone} purpose=login code=(\\d{6})`, "g");
  for (let i = 0; i < 20; i++) {
    const log = execSync(otpLogCommand!, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    const matches = [...log.matchAll(re)];
    if (matches.length > 0) return matches[matches.length - 1][1];
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("OTP not found in backend log");
}

test.describe("purchase journey (needs E2E_OTP_LOG_COMMAND)", () => {
  test.skip(!otpLogCommand, "E2E_OTP_LOG_COMMAND not set");

  test("browse, add to cart, sign in with OTP, check out, see the order Django created", async ({ page }) => {
    // Storefront -> product list -> product detail
    await page.goto("/en");
    await page.goto("/en/products");
    await page.locator(`a[href$="/products/${PRODUCT}"]`).first().click();
    await expect(page).toHaveURL(new RegExp(`/en/products/${PRODUCT}`));
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Hoodie 10");

    // Anonymous add to cart is refused by Django (401) and the UI offers sign-in instead of success.
    await page.getByRole("radio", { name: "M" }).check({ force: true });
    await page.getByRole("button", { name: "Add to cart" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Sign in to use your cart." })).toBeVisible();
    await expect(page.getByText("Added to your cart.")).toHaveCount(0);

    // Real OTP sign-in UI, returning to this product.
    const local = `0912${String(Date.now() % 1_000_000).padStart(6, "0")}7`;
    await page.goto(`/en/sign-in?next=${encodeURIComponent(`/en/products/${PRODUCT}`)}`);
    await page.getByLabel("Mobile number").fill(local);
    await page.getByRole("button", { name: "Send code" }).click();
    await expect(page.getByLabel("Verification code")).toBeVisible();
    await page.getByLabel("Verification code").fill(await readOtp(`+98${local.slice(1)}`));
    await page.getByRole("button", { name: "Verify and sign in" }).click();
    await expect(page).toHaveURL(new RegExp(`/en/products/${PRODUCT}`));

    // Add to cart (real CSRF + session through Nginx), then open the cart.
    await page.getByRole("radio", { name: "M" }).check({ force: true });
    await page.getByRole("button", { name: "Add to cart" }).click();
    await expect(page.getByText("Added to your cart.")).toBeVisible();
    await page.getByRole("link", { name: "View cart" }).click();
    await expect(page).toHaveURL(/\/en\/cart$/);

    // The cart shown is exactly what the server returns.
    const cart = await (await page.request.get("/api/cart/")).json();
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].variant_size.sku).toBe(`${PRODUCT}-black-m`);
    await expect(page.getByTestId("cart-line")).toHaveCount(1);
    await expect(page.getByTestId("cart-total")).toHaveText(money(cart.total));

    // Checkout: five delivery fields, order confirmed only after Django's 201.
    await page.getByRole("link", { name: "Proceed to checkout" }).click();
    await expect(page).toHaveURL(/\/en\/checkout$/);
    await page.getByLabel("Recipient name").fill("Sara Ahmadi");
    await page.getByLabel("Province").fill("Tehran");
    await page.getByLabel("City").fill("Tehran");
    await page.getByLabel("Address").fill("Valiasr St, No. 12");
    await page.getByLabel("Postal code").fill("1234567890");
    const posted = page.waitForResponse((r) => r.url().endsWith("/api/orders/") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Place order" }).click();
    expect((await posted).status()).toBe(201);
    await expect(page.getByRole("heading", { name: "Order placed" })).toBeVisible();

    // Backend state: one order, server-computed total, snapshot lines, cart emptied.
    const orders = await (await page.request.get("/api/orders/")).json();
    expect(orders).toHaveLength(1);
    expect(orders[0].total).toBe(cart.total);
    expect(orders[0].payment_status).toBe("unpaid");
    expect(orders[0].items).toHaveLength(1);
    expect(orders[0].items[0].sku).toBe(`${PRODUCT}-black-m`);
    expect(orders[0].items[0].unit_price).toBe(cart.items[0].unit_price);
    await expect(page.getByTestId("order-id")).toHaveText(String(orders[0].id));
    expect((await (await page.request.get("/api/cart/")).json()).items).toHaveLength(0);
  });
});
