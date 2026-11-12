import { expect, test, type Page, type Route } from "./fixtures";
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
const codeInput = (page: Page) => page.getByLabel("کد تأیید پیامکی");
const sendButton = (page: Page) => page.getByRole("button", { name: "دریافت کد تأیید" });
const verifyButton = (page: Page) => page.getByRole("button", { name: "تأیید شماره و ادامه" });
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
    await expect(page.getByRole("heading", { name: "حساب کاربری ودزمانی", level: 1 })).toBeVisible();
    await sendButton(page).click();
    await expect(page.getByText("شماره موبایل را وارد کنید.")).toBeVisible();
    await expect(phoneInput(page)).toBeFocused();
  });

  test("ثبت‌نام حالت پیش‌فرض است و فرم ورود رمز عبور را نمایش می‌دهد", async ({ page }) => {
    await page.goto("/fa/sign-in");
    await expect(page.getByRole("heading", { name: "حساب کاربری ودزمانی", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "ورود به حساب" }).click();
    const password = page.getByLabel("رمز عبور");
    await expect(password).toBeVisible();
    await expect(password).toHaveAttribute("type", "password");
    const showPassword = page.getByRole("button", { name: "نمایش رمز" });
    await expect(showPassword.locator("svg")).toBeVisible();
    const inputBox = await password.boundingBox();
    const toggleBox = await showPassword.boundingBox();
    expect(inputBox).not.toBeNull();
    expect(toggleBox).not.toBeNull();
    expect(toggleBox!.x).toBeGreaterThan(inputBox!.x + inputBox!.width / 2);
    await showPassword.click();
    await expect(password).toHaveAttribute("type", "text");
    const hidePassword = page.getByRole("button", { name: "مخفی کردن رمز" });
    await expect(hidePassword.locator("svg")).toBeVisible();
    await hidePassword.click();
    await expect(password).toHaveAttribute("type", "password");
  });

  test("هنگام ارسال کد، دکمه وضعیت انتظار را واضح نشان می‌دهد", async ({ page }) => {
    let releaseRequest!: () => void;
    const requestGate = new Promise<void>((resolve) => { releaseRequest = resolve; });
    await mockRequest(page, async (route) => {
      await requestGate;
      await route.fulfill({ status: 202, json: { detail: "OTP request accepted." } });
    });
    await page.goto("/fa/sign-in");
    await phoneInput(page).fill("09120000009");
    const submit = sendButton(page);
    await submit.click();
    const loading = page.getByTestId("auth-send-code");
    await expect(loading).toHaveAttribute("aria-label", "در حال ارسال...");
    await expect(loading).toBeDisabled();
    releaseRequest();
    await expect(codeInput(page)).toBeVisible();
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
    await expect(alertBox(page)).toContainText("ارسال پیامک فعلاً فعال نیست");
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
    await expect(alertBox(page)).toContainText("کد منقضی شده است");
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
    await page.getByRole("button", { name: "ویرایش شماره" }).click();
    await expect(phoneInput(page)).toHaveValue("09120000006");
    await expect(codeInput(page)).toHaveCount(0);
  });
});

test.describe("دسترسی مهمان", () => {
  test("سبد خالی مهمان بدون اجبار به ورود قابل مشاهده است", async ({ page }) => {
    await page.goto("/fa/cart");
    await expect(page.getByRole("heading", { name: "سبد خرید", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "سبد خرید شما خالی است" })).toBeVisible();
    await expect(page.locator("section[aria-labelledby='empty-cart-title']")).toHaveClass(/text-center/);
    await expect(page.getByRole("link", { name: "مشاهده محصولات" })).toHaveAttribute("href", "/fa/products");
  });

  test("checkout مسیر بازگشت به خرید را در لینک ورود نگه می‌دارد", async ({ page }) => {
    await page.goto("/fa/checkout");
    await expect(page.getByRole("heading", { name: "برای ادامه وارد شوید یا حساب بسازید" })).toBeVisible();
    await expect(page.getByRole("link", { name: "ورود / ساخت حساب" })).toHaveAttribute("href", "/fa/sign-in?next=%2Ffa%2Fcheckout");
  });

  test("پروفایل مهمان مسیر بازگشت امن را حفظ می‌کند", async ({ page }) => {
    await page.goto("/fa/profile");
    await expect(page.getByRole("heading", { name: "پروفایل", level: 1 })).toBeVisible();
    await expect(page.locator("section[aria-labelledby='profile-signed-out-title']")).toHaveClass(/text-center/);
    await expect(page.getByRole("link", { name: "ورود / ساخت حساب" })).toHaveAttribute("href", "/fa/sign-in?next=%2Ffa%2Fprofile");
  });
});

test.describe("جریان واقعی کد یک‌بارمصرف", () => {
  test.skip(!otpLogCommand, "E2E_OTP_LOG_COMMAND is not set");

  test("ورود واقعی با OTP و بازگشت مستقیم به checkout", async ({ page }) => {
    const phone = uniquePhone();
    await page.goto(`/fa/sign-in?next=${encodeURIComponent("/fa/checkout")}`);
    await phoneInput(page).fill(phone);
    await sendButton(page).click();
    await expect(codeInput(page)).toBeVisible();
    await codeInput(page).fill(await readOtp(phone));
    await verifyButton(page).click();
    await expect(page.getByRole("heading", { name: "برای حساب خود رمز بسازید" })).toBeVisible();
    await page.getByLabel("رمز عبور", { exact: true }).fill("Secure-Vedzmani-2026!");
    await page.getByLabel("تکرار رمز عبور").fill("Secure-Vedzmani-2026!");
    await page.getByRole("button", { name: "ثبت رمز عبور" }).click();
    await expect(page).toHaveURL(/checkout$/);
    await expect(page.getByRole("heading", { name: "سبد خرید شما خالی است" })).toBeVisible();
    const me = await (await page.request.get("/api/auth/me/")).json();
    expect(me.phone).toBe(canonical(phone));
  });
});
