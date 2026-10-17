import { expect, test, type Page, type Route } from "@playwright/test";
import { execSync } from "node:child_process";

/**
 * Customer OTP sign-in e2e (Nginx -> Next + Django).
 *
 * Tests WITHOUT "(mocked response)" call the real Django API. Tests that need a real OTP also need
 *   E2E_OTP_LOG_COMMAND  a shell command that prints the TEST backend's log, e.g.
 *     docker compose -p vedzmani-agenti logs --no-color backend
 * The test backend runs config.settings.dev, whose DEV-ONLY ConsoleDelivery writes
 * "DEV OTP delivery: phone=... code=..." to the log. That is NOT SMS delivery; no SMS provider is
 * configured. Never point this at a stack with real customers: it reads codes from a log.
 * Each test uses its own phone number (Django has a per-phone 60 s resend cooldown). The throwaway
 * stack should raise OTP_REQUEST_IP_LIMIT / OTP_VERIFY_IP_LIMIT (see e2e/README-signin.md).
 * Tests named "(mocked response)" intercept one auth call to produce failures that cannot be
 * produced on demand (503 without a provider, 429, network loss, expired code); they assert UI only.
 */

const otpLogCommand = process.env.E2E_OTP_LOG_COMMAND;

let counter = 0;
function uniquePhone(): string {
  counter += 1;
  const tail = String(Date.now() % 1_000_000).padStart(6, "0");
  return `0912${tail}${counter % 10}`;
}
const canonical = (local: string) => `+98${local.slice(1)}`;

async function readOtp(local: string): Promise<string> {
  if (!otpLogCommand) throw new Error("E2E_OTP_LOG_COMMAND is required");
  const re = new RegExp(`phone=\\${canonical(local)} purpose=login code=(\\d{6})`, "g");
  for (let i = 0; i < 20; i++) {
    const log = execSync(otpLogCommand, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    const matches = [...log.matchAll(re)];
    if (matches.length > 0) return matches[matches.length - 1][1];
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("OTP not found in backend log");
}

const phoneInput = (page: Page) => page.getByLabel("Mobile number");
const codeInput = (page: Page) => page.getByLabel("Verification code");
const sendButton = (page: Page) => page.getByRole("button", { name: "Send code" });
const verifyButton = (page: Page) => page.getByRole("button", { name: "Verify and sign in" });
/** Form alerts only: Next's route announcer is also role=alert. */
const alertBox = (page: Page) => page.locator('form [role="alert"]');
const resendButton = (page: Page) => page.getByRole("button", { name: /Resend code/ });

const json = (status: number, body: unknown, headers: Record<string, string> = {}) => (route: Route) =>
  route.fulfill({ status, json: body, headers });
const err = (code: string, message = "x") => ({ error: { code, message } });

async function mockRequest(page: Page, handler: (route: Route) => unknown) {
  await page.route("**/api/auth/otp/request/", handler as never);
}
async function mockVerify(page: Page, handler: (route: Route) => unknown) {
  await page.route("**/api/auth/otp/verify/", handler as never);
}
/** Reaches the code step with a mocked 202 so verify-side failures can be mocked. */
async function toCodeStepMocked(page: Page, local = "09120000001") {
  await mockRequest(page, json(202, { detail: "OTP request accepted." }));
  await page.goto("/en/sign-in");
  await phoneInput(page).fill(local);
  await sendButton(page).click();
  await expect(codeInput(page)).toBeVisible();
}

test.describe("sign-in page", () => {
  test("renders the phone step; empty submit shows a validation error and sends no request", async ({ page }) => {
    let requests = 0;
    page.on("request", (r) => r.url().includes("/api/auth/otp/request/") && requests++);
    await page.goto("/en/sign-in");
    await expect(page.getByRole("heading", { name: "Sign in", level: 1 })).toBeVisible();
    await sendButton(page).click();
    await expect(page.getByText("Enter your mobile number.")).toBeVisible();
    await expect(phoneInput(page)).toBeFocused();
    expect(requests).toBe(0);
  });

  test("Persian locale renders RTL with Persian copy", async ({ page }) => {
    await page.goto("/fa/sign-in");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { name: "ورود", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "ارسال کد" })).toBeVisible();
  });

  test("an invalid phone is rejected by Django and the customer stays on the phone step", async ({ page }) => {
    await page.goto("/en/sign-in");
    await phoneInput(page).fill("123");
    await sendButton(page).click();
    await expect(page.getByText("Enter a valid Iranian mobile number")).toBeVisible();
    await expect(codeInput(page)).toHaveCount(0);
    await expect(phoneInput(page)).toHaveAttribute("aria-invalid", "true");
  });

  test("503 delivery unavailable (mocked response) keeps the phone step and claims no delivery", async ({ page }) => {
    await mockRequest(page, json(503, err("otp_delivery_unavailable")));
    await page.goto("/en/sign-in");
    await phoneInput(page).fill("09120000002");
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText("can't send verification codes right now");
    await expect(codeInput(page)).toHaveCount(0);
    await expect(sendButton(page)).toBeEnabled();
  });

  test("429 rate_limited with Retry-After (mocked response) shows the wait time", async ({ page }) => {
    await mockRequest(page, json(429, err("rate_limited"), { "Retry-After": "120" }));
    await page.goto("/en/sign-in");
    await phoneInput(page).fill("09120000003");
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText("Try again in 2 minutes");
    await expect(codeInput(page)).toHaveCount(0);
  });

  test("network failure on request (mocked response) shows a connection message", async ({ page }) => {
    await mockRequest(page, (route) => route.abort("failed"));
    await page.goto("/en/sign-in");
    await phoneInput(page).fill("09120000004");
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText("Could not reach the store");
    await expect(codeInput(page)).toHaveCount(0);
  });

  test("unexpected success body on request (mocked response) is not treated as sent", async ({ page }) => {
    await mockRequest(page, json(202, { surprise: true }));
    await page.goto("/en/sign-in");
    await phoneInput(page).fill("09120000005");
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText("unexpected response");
    await expect(codeInput(page)).toHaveCount(0);
  });

  test("verify errors (mocked response): expired, attempts exceeded, rate limited and disabled are distinct", async ({ page }) => {
    await toCodeStepMocked(page);
    const cases: [number, string, string, Record<string, string>?][] = [
      [400, "otp_expired", "This code has expired", undefined],
      [429, "otp_attempts_exceeded", "Too many incorrect attempts", { "Retry-After": "30" }],
      [429, "rate_limited", "Try again in 30 seconds", { "Retry-After": "30" }],
      [403, "account_disabled", "This account is disabled", undefined],
      [403, "csrf_failed", "secure session could not be verified", undefined],
    ];
    for (const [status, code, text, headers] of cases) {
      await page.unroute("**/api/auth/otp/verify/");
      await mockVerify(page, json(status, err(code), headers));
      await codeInput(page).fill("123456");
      await verifyButton(page).click();
      await expect(alertBox(page)).toContainText(text);
      await expect(verifyButton(page)).toBeEnabled();
      if (code === "rate_limited") await expect(alertBox(page)).not.toContainText("incorrect attempts");
    }
  });

  test("verify network loss (mocked response) while NOT signed in shows an error", async ({ page }) => {
    await toCodeStepMocked(page);
    await mockVerify(page, (route) => route.abort("failed"));
    await codeInput(page).fill("123456");
    await verifyButton(page).click();
    await expect(alertBox(page)).toContainText("Could not reach the store");
  });

  test("empty code and bad format are rejected without wasting an attempt (mocked response)", async ({ page }) => {
    await toCodeStepMocked(page);
    let verifies = 0;
    await mockVerify(page, (route) => {
      verifies++;
      return json(400, { error: { code: "validation_error", message: "x", details: { code: [{ code: "invalid_code_format", message: "x" }] } } })(route);
    });
    await verifyButton(page).click();
    await expect(page.getByText("Enter the verification code.")).toBeVisible();
    expect(verifies).toBe(0);
    await codeInput(page).fill("12");
    await verifyButton(page).click();
    await expect(page.getByText("Enter the 6-digit code.", { exact: true })).toBeVisible();
    await expect(codeInput(page)).toHaveValue("12");
  });

  test("change number returns to the phone step with the number kept; resend honours a 60 s cooldown (mocked response)", async ({ page }) => {
    await page.clock.install();
    await toCodeStepMocked(page, "09120000006");
    await expect(page.getByText("09120000006")).toBeVisible();
    await expect(resendButton(page)).toBeDisabled();
    await expect(resendButton(page)).toContainText("Resend code in");
    await page.clock.fastForward(61_000);
    await expect(resendButton(page)).toBeEnabled();
    await resendButton(page).click();
    await expect(page.getByText("A new code was requested.")).toBeVisible();
    await expect(resendButton(page)).toBeDisabled();

    await page.getByRole("button", { name: "Change number" }).click();
    await expect(phoneInput(page)).toHaveValue("09120000006");
    await expect(codeInput(page)).toHaveCount(0);
  });
});

test.describe("anonymous entry points", () => {
  for (const [path, next] of [
    ["/en/cart", "/en/cart"],
    ["/en/checkout", "/en/checkout"],
    ["/en/profile", "/en/profile"],
  ] as const) {
    test(`${path} offers a sign-in link that returns here`, async ({ page }) => {
      await page.goto(path);
      const link = page.getByRole("link", { name: "Sign in", exact: true }).last();
      await expect(link).toHaveAttribute("href", `/en/sign-in?next=${encodeURIComponent(next)}`);
    });
  }

  test("checkout keeps its 'Sign in to continue' heading", async ({ page }) => {
    await page.goto("/en/checkout");
    await expect(page.getByRole("heading", { name: "Sign in to continue" })).toBeVisible();
  });

  test("add to cart as an anonymous visitor offers sign-in back to the product", async ({ page }) => {
    await page.goto("/en/products/e2e-hoodie-02");
    await page.locator("label", { hasText: /^M$/ }).first().click();
    await page.getByRole("button", { name: /add to cart/i }).click();
    const link = page.getByRole("alert").getByRole("link", { name: "Sign in" });
    await expect(link).toHaveAttribute("href", `/en/sign-in?next=${encodeURIComponent("/en/products/e2e-hoodie-02")}`);
  });
});

test.describe("real OTP flow (needs E2E_OTP_LOG_COMMAND)", () => {
  test.skip(!otpLogCommand, "E2E_OTP_LOG_COMMAND not set");

  async function requestCode(page: Page, local: string, next?: string) {
    await page.goto(next ? `/en/sign-in?next=${encodeURIComponent(next)}` : "/en/sign-in");
    await phoneInput(page).fill(local);
    await sendButton(page).click();
    await expect(codeInput(page)).toBeVisible();
  }

  test("phone -> code -> signed in, returned to /en/checkout, session is real", async ({ page }) => {
    const local = uniquePhone();
    const csrfRequests: string[] = [];
    page.on("request", (r) => r.url().includes("/api/auth/otp/") && csrfRequests.push(r.headers()["x-csrftoken"] ?? ""));
    await requestCode(page, local, "/en/checkout");
    await expect(page.getByText(local)).toBeVisible();

    await codeInput(page).fill(await readOtp(local));
    await verifyButton(page).click();

    await expect(page).toHaveURL(/\/en\/checkout$/);
    await expect(page.getByRole("heading", { name: "Your cart is empty" })).toBeVisible();
    const me = await (await page.request.get("/api/auth/me/")).json();
    expect(me.phone).toBe(canonical(local));
    expect(csrfRequests.length).toBe(2);
    expect(csrfRequests.every((t) => t.length > 10)).toBe(true);

    // Already signed in: the sign-in page forwards to the destination.
    await page.goto("/en/sign-in?next=/en/cart");
    await expect(page).toHaveURL(/\/en\/cart$/);
  });

  test("wrong code is rejected and cleared, then the right code works", async ({ page }) => {
    const local = uniquePhone();
    await requestCode(page, local, "/en/profile");
    const good = await readOtp(local);
    const wrong = good === "000000" ? "111111" : "000000";

    await codeInput(page).fill(wrong);
    await verifyButton(page).click();
    await expect(page.getByText("That code is not correct.")).toBeVisible();
    await expect(codeInput(page)).toHaveValue("");
    await expect(page).toHaveURL(/sign-in/);

    await codeInput(page).fill(good);
    await verifyButton(page).click();
    await expect(page).toHaveURL(/\/en\/profile$/);
    await expect(page.getByText(canonical(local))).toBeVisible();
  });

  test("a code cannot be reused (consumed) after a successful sign-in elsewhere", async ({ page, browser }) => {
    const local = uniquePhone();
    await requestCode(page, local);
    const code = await readOtp(local);
    const other = await browser.newContext();
    const p2 = await other.newPage();
    await p2.goto("/en/sign-in");
    // Consume the code through the API directly from a second browser context.
    const csrf = (await (await p2.request.get("/api/auth/csrf/")).json()).csrfToken;
    const res = await p2.request.post("/api/auth/otp/verify/", { data: { phone: local, code }, headers: { "X-CSRFToken": csrf } });
    expect(res.status()).toBe(200);
    await other.close();

    await codeInput(page).fill(code);
    await verifyButton(page).click();
    await expect(alertBox(page)).toContainText("already used");
  });

  test("an unsafe ?next= falls back to the profile page after a real sign-in", async ({ page }) => {
    const local = uniquePhone();
    await requestCode(page, local, "//evil.example/en/cart");
    await codeInput(page).fill(await readOtp(local));
    await verifyButton(page).click();
    await expect(page).toHaveURL(/\/en\/profile$/);
    expect(new URL(page.url()).host).not.toContain("evil");
  });

  test("a second request for the same number inside the cooldown is rate limited by Django", async ({ page }) => {
    const local = uniquePhone();
    await requestCode(page, local);
    await page.getByRole("button", { name: "Change number" }).click();
    await sendButton(page).click();
    await expect(alertBox(page)).toContainText(/Try again in \d+ seconds?|Too many requests/);
    await expect(codeInput(page)).toHaveCount(0);
  });
});
