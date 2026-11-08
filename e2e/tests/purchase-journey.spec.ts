import { expect, test } from "@playwright/test";
import { execSync } from "node:child_process";

/**
 * End-to-end guest purchase preparation:
 * storefront -> product -> guest cart -> OTP account creation -> authenticated checkout.
 * Final order placement intentionally remains disabled until a payment gateway is integrated.
 */
const otpLogCommand = process.env.E2E_OTP_LOG_COMMAND;
const PRODUCT = "e2e-hoodie-10";

async function readOtp(canonicalPhone: string): Promise<string> {
  const prefix = `phone=${canonicalPhone} purpose=login code=`;
  for (let i = 0; i < 20; i++) {
    const log = execSync(otpLogCommand!, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    const line = log.split(/\r?\n/).filter((entry) => entry.includes(prefix)).at(-1);
    const match = line?.match(/code=(\d{6})/);
    if (match) return match[1];
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("OTP not found in backend log");
}

test.describe("purchase journey (needs E2E_OTP_LOG_COMMAND)", () => {
  test.skip(!otpLogCommand, "E2E_OTP_LOG_COMMAND not set");

  test("guest adds product, creates account with OTP and reaches payment-safe checkout", async ({ page }) => {
    let orderPosts = 0;
    page.on("request", (request) => {
      if (request.url().includes("/api/orders/") && request.method() === "POST") orderPosts += 1;
    });

    await page.goto(`/fa/products/${PRODUCT}`);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Hoodie 10");
    await page.locator("label").filter({ has: page.getByRole("radio", { name: "M" }) }).click();
    await page.getByRole("button", { name: "افزودن به سبد خرید" }).click();
    await expect(page.getByText("به سبد خرید اضافه شد.")).toBeVisible();
    await page.getByRole("link", { name: "سبد خرید، ۱ کالا" }).click();
    await expect(page).toHaveURL(/cart$/);
    await expect(page.getByTestId("guest-cart-line")).toBeVisible();

    await page.getByRole("link", { name: "تکمیل خرید" }).click();
    await expect(page).toHaveURL(/sign-in/);
    const phone = `0912${String(Date.now() % 1_000_000).padStart(6, "0")}7`;
    await page.getByLabel("شماره موبایل").fill(phone);
    await page.getByRole("button", { name: "دریافت کد تأیید" }).click();
    await expect(page.getByLabel("کد تأیید پیامکی")).toBeVisible();
    await page.getByLabel("کد تأیید").fill(await readOtp(`+98${phone.slice(1)}`));
    await page.getByRole("button", { name: "تأیید شماره و ادامه" }).click();
    await expect(page.getByRole("heading", { name: "برای حساب خود رمز بسازید" })).toBeVisible();
    await page.getByLabel("رمز عبور", { exact: true }).fill("Secure-Vedzmani-2026!");
    await page.getByLabel("تکرار رمز عبور").fill("Secure-Vedzmani-2026!");
    await page.getByRole("button", { name: "ثبت رمز عبور" }).click();

    await expect(page).toHaveURL(/checkout$/);
    await expect(page.getByRole("heading", { name: "اطلاعات تحویل" })).toBeVisible();
    await expect(page.getByText("Hoodie 10")).toBeVisible();
    await expect(page.getByLabel("نام گیرنده")).toBeVisible();
    await expect(page.getByLabel("استان")).toBeVisible();
    await expect(page.getByLabel("شهر")).toBeVisible();
    await expect(page.getByLabel("نشانی کامل")).toBeVisible();
    await expect(page.getByLabel("کد پستی")).toBeVisible();
    await expect(page.getByRole("button", { name: "ثبت سفارش" })).toHaveCount(0);
    expect(orderPosts).toBe(0);

    const cart = await (await page.request.get("/api/cart/")).json();
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].variant_size.sku).toBe(`${PRODUCT}-black-m`);
    expect((await (await page.request.get("/api/auth/me/")).json()).phone).toBe(`+98${phone.slice(1)}`);
  });
});
