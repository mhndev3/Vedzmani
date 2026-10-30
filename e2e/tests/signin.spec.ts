import { expect, test, type Page, type Route } from "@playwright/test";
import { execSync } from "node:child_process";

const otpLogCommand = process.env.E2E_OTP_LOG_COMMAND;
let counter = 0;
function uniquePhone(): string {
  counter += 1;
  return `0912${String(Date.now() % 1_000_000).padStart(6, "0")}${counter % 10}`;
}
const canonical = (local: string) => `+98${local.slice(1)}`;

async function readOtp(local: string): Promise<string> {
  if (!otpLogCommand) throw new Error("E2E_OTP_LOG_COMMAND is required");
  const re = new RegExp(`phone=\\${canonical(local)} purpose=login code=(\\d{6})`, "g");
  for (let i = 0; i < 20; i++) {
    const log = execSync(otpLogCommand, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    const matches = [...log.matchAll(re)];
    if (matches.length) return matches[matches.length - 1][1];
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("OTP not found in backend log");
}

const phoneInput = (page: Page) => page.getByLabel("شماره موبایل");
const codeInput = (page: Page) => page.getByLabel("کد تأیید");
const sendButton = (page: Page) => page.getByRole("button", { name: "ارسال کد" });
const verifyButton = (page: Page) => page.getByRole("button", { name: "تأیید و ورود" });
const alertBox = (page: Page) => page.locator('form [role="alert"]');
const json = (status: number, body: unknown, headers: Record<string, string> = {}) => (route: Route) =>
  route.fulfill({ status, json: body, headers });
const err = (code: string) => ({ error: { code, message: "x" } });

async function mockRequest(page: Page, handler: (route: Route) => unknown) {
  await page.route("**/api/auth/otp/request/", handler as never);
}
async function mockVerify(page: Page, handler: (route: Route) => unknown) {
  await page.route("**/api/auth/otp/verify/", handler as never);
}
async function toCodeStepMocked(page: Page, phone = "09120000001") {
  await mockRequest(page, json(202, { detail: "OTP request accepted." }));
  await page.goto("/fa/sign-in");
  await phoneInput(page).fill(phone);
  await sendButton(page).click();
  await expect(codeInput(page)).toBeVisible();
}

test.describe("ورود با شماره موبایل", () => {
  test("صفحه فارسی و راست‌چین است و ارسال فرم خالی اعتبارسنجی می‌شود", async ({ page }) => {
    await page.goto("/fa/sign-in");
    await expect(page.locator("html")).toHaveAttribute("lang", "fa");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { name: "ورود", level: 1 })).toBeVisible();
    await sendButton(page).click();
    await expect(page.getByText("شماره موبایل را وارد کنید.")).toBeVisible();
    await expect(phoneInput(page)).toBeFocused();
  });

  test("شماره نامعتبر در سرور رد می‌شود", async ({ page }) => {
    await page.goto("/fa/sign-in");
    await phoneInput(page).fill("123");
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText("شماره موبایل معتبر ایران");
    await expect(codeInput(page)).toHaveCount(0);
  });

  test("نبود سرویس ارسال کد، موفقیت جعلی نشان نمی‌دهد", async ({ page }) => {
    await mockRequest(page, json(503, err("otp_delivery_unavailable")));
    await page.goto("/fa/sign-in");
    await phoneInput(page).fill("09120000002");
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText("در حال حاضر ارسال کد تأیید ممکن نیست");
    await expect(codeInput(page)).toHaveCount(0);
  });

  test("محدودیت درخواست با پیام فارسی نشان داده می‌شود", async ({ page }) => {
    await mockRequest(page, json(429, err("rate_limited"), { "Retry-After": "120" }));
    await page.goto("/fa/sign-in");
    await phoneInput(page).fill("09120000003");
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText("تعداد درخواست‌ها زیاد است");
    await expect(codeInput(page)).toHaveCount(0);
  });

  test("قطع شبکه پیام اتصال نشان می‌دهد", async ({ page }) => {
    await mockRequest(page, (route) => route.abort("failed"));
    await page.goto("/fa/sign-in");
    await phoneInput(page).fill("09120000004");
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText("ارتباط با فروشگاه برقرار نشد");
    await expect(codeInput(page)).toHaveCount(0);
  });

  test("خطای انقضای کد و تلاش ناموفق قابل تشخیص است", async ({ page }) => {
    await toCodeStepMocked(page);
    await mockVerify(page, json(400, err("otp_expired")));
    await codeInput(page).fill("123456");
    await verifyButton(page).click();
    await expect(alertBox(page)).toContainText("این کد منقضی شده است");
    await expect(verifyButton(page)).toBeEnabled();
  });

  test("کد خالی بدون درخواست تأیید رد می‌شود", async ({ page }) => {
    await toCodeStepMocked(page);
    let attempts = 0;
    await mockVerify(page, (route) => {
      attempts += 1;
      return json(400, err("otp_invalid"))(route);
    });
    await verifyButton(page).click();
    await expect(page.getByText("کد تأیید را وارد کنید.")).toBeVisible();
    expect(attempts).toBe(0);
  });

  test("تغییر شماره به مرحله اول بازمی‌گردد", async ({ page }) => {
    await toCodeStepMocked(page, "09120000006");
    await page.getByRole("button", { name: "تغییر شماره" }).click();
    await expect(phoneInput(page)).toHaveValue("09120000006");
    await expect(codeInput(page)).toHaveCount(0);
  });
});

test.describe("دسترسی مهمان", () => {
  for (const path of ["/fa/cart", "/fa/checkout", "/fa/profile"]) {
    test(`${path} مسیر ورود را حفظ می‌کند`, async ({ page }) => {
      await page.goto(path);
      const link = page.getByRole("link", { name: "ورود", exact: true }).last();
      await expect(link).toHaveAttribute("href", `/fa/sign-in?next=${encodeURIComponent(path)}`);
    });
  }

  test("تسویه حساب مهمان را به ورود هدایت می‌کند", async ({ page }) => {
    await page.goto("/fa/checkout");
    await expect(page.getByRole("heading", { name: "برای ادامه وارد شوید" })).toBeVisible();
  });
});

test.describe("جریان واقعی کد یک‌بارمصرف", () => {
  test.skip(!otpLogCommand, "E2E_OTP_LOG_COMMAND is not set");

  test("ورود واقعی به حساب و بازگشت به مقصد امن", async ({ page }) => {
    const phone = uniquePhone();
    await page.goto(`/fa/sign-in?next=${encodeURIComponent("/fa/checkout")}`);
    await phoneInput(page).fill(phone);
    await sendButton(page).click();
    await expect(codeInput(page)).toBeVisible();
    await codeInput(page).fill(await readOtp(phone));
    await verifyButton(page).click();
    await expect(page).toHaveURL(/\/fa\/checkout$/);
    await expect(page.getByRole("heading", { name: "سبد خرید شما خالی است" })).toBeVisible();
    const me = await (await page.request.get("/api/auth/me/")).json();
    expect(me.phone).toBe(canonical(phone));
  });
});
