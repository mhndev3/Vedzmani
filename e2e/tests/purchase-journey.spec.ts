import { expect, test } from "@playwright/test";
import { execSync } from "node:child_process";

/**
 * Purchase journey smoke test, driven entirely through the UI:
 *   storefront -> product -> size -> add to cart -> cart -> OTP sign-in -> checkout -> order confirmation.
 *
 * STATUS: runs in the E2E workflow (.github/workflows/e2e.yml) on a disposable Compose stack. That
 * workflow's report check (e2e/scripts/report-summary.mjs) fails the job if this test is missing, is
 * skipped, or does not pass on its first attempt. To run it locally see e2e/README-purchase-journey.md.
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
const money = (value: string) => `${new Intl.NumberFormat("fa-IR").format(Number(value))} تومان`;

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
    await page.goto("/fa");
    await page.goto("/fa/products");
    await page.locator(`a[href$="/products/${PRODUCT}"]`).first().click();
    await expect(page).toHaveURL(new RegExp(`/fa/products/${PRODUCT}`));
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Hoodie 10");

    await page.locator("label").filter({ has: page.getByRole("radio", { name: "M" }) }).click();
    await page.getByRole("button", { name: "افزودن به سبد خرید" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "برای استفاده از سبد خرید وارد شوید." })).toBeVisible();
    await expect(page.getByText("به سبد خرید اضافه شد.")).toHaveCount(0);

    const local = `0912${String(Date.now() % 1_000_000).padStart(6, "0")}7`;
    await page.goto(`/fa/sign-in?next=${encodeURIComponent(`/fa/products/${PRODUCT}`)}`);
    await page.getByLabel("شماره موبایل").fill(local);
    await page.getByRole("button", { name: "ارسال کد" }).click();
    await expect(page.getByLabel("کد تأیید")).toBeVisible();
    await page.getByLabel("کد تأیید").fill(await readOtp(`+98${local.slice(1)}`));
    await page.getByRole("button", { name: "تأیید و ورود" }).click();
    await expect(page).toHaveURL(/\/fa\/profile\?next=/);
    await expect(page.getByRole("heading", { name: "تکمیل اطلاعات حساب کاربری" })).toBeVisible();
    await page.getByLabel("نام", { exact: true }).fill("Sara");
    await page.getByLabel("نام خانوادگی", { exact: true }).fill("Ahmadi");
    await page.getByLabel("نشانی کامل", { exact: true }).fill("Valiasr St, No. 12");
    await page.getByLabel("کد پستی", { exact: true }).fill("1234567890");
    await page.getByLabel("کد ملی", { exact: true }).fill(local.slice(-10));
    await page.getByRole("button", { name: "ذخیره اطلاعات" }).click();
    await expect(page).toHaveURL(new RegExp(`/fa/products/${PRODUCT}`));

    await page.locator("label").filter({ has: page.getByRole("radio", { name: "M" }) }).click();
    await page.getByRole("button", { name: "افزودن به سبد خرید" }).click();
    await expect(page.getByText("به سبد خرید اضافه شد.")).toBeVisible();
    await expect(page.getByRole("link", { name: "سبد خرید، ۱ کالا" })).toBeVisible();
    await page.getByRole("link", { name: "مشاهده سبد خرید" }).click();
    await expect(page).toHaveURL(/\/fa\/cart$/);

    const cart = await (await page.request.get("/api/cart/")).json();
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].variant_size.sku).toBe(`${PRODUCT}-black-m`);
    await expect(page.getByTestId("cart-line")).toHaveCount(1);
    await expect(page.getByTestId("cart-total")).toHaveText(money(cart.total));

    await page.getByRole("link", { name: "ادامه به ثبت سفارش" }).click();
    await expect(page).toHaveURL(/\/fa\/checkout$/);
    await page.getByLabel("نام گیرنده").fill("Sara Ahmadi");
    await page.getByLabel("استان").fill("Tehran");
    await page.getByLabel("شهر").fill("Tehran");
    await page.getByLabel("نشانی").fill("Valiasr St, No. 12");
    await page.getByLabel("کد پستی").fill("1234567890");
    const posted = page.waitForResponse((r) => r.url().endsWith("/api/orders/") && r.request().method() === "POST");
    await page.getByRole("button", { name: "ثبت سفارش" }).click();
    expect((await posted).status()).toBe(201);
    await expect(page.getByRole("heading", { name: "سفارش ثبت شد" })).toBeVisible();

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
