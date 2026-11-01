import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

const backendDir = process.env.E2E_BACKEND_DIR;
const python = process.env.E2E_PYTHON ?? "python";
const helperPath = path.join(__dirname, "..", "e2e_helper.py");

type Session = { sessionid: string; phone: string; variantSizeIds: Record<string, number> };
function helper<T>(env: Record<string, string>): T {
  if (!backendDir) throw new Error("E2E_BACKEND_DIR is required");
  const out = execFileSync(
    python,
    ["manage.py", "shell", "-c", `exec(open(${JSON.stringify(helperPath)}, encoding="utf-8").read())`],
    { cwd: backendDir, env: { ...process.env, ...env }, encoding: "utf8" },
  );
  const line = out.split(/\r?\n/).find((value) => value.startsWith("E2E_JSON:"));
  if (!line) throw new Error(`helper produced no result:\n${out}`);
  return JSON.parse(line.slice("E2E_JSON:".length)) as T;
}

let counter = 0;
function uniquePhone(): string {
  counter += 1;
  return `0912${String(Date.now() % 1_000_000).padStart(6, "0")}${counter % 10}`;
}
async function createSession(): Promise<Session> {
  return helper<Session>({ E2E_ACTION: "session", E2E_PHONE: uniquePhone() });
}
async function applySession(page: Page, session: Session, baseURL: string) {
  await page.context().addCookies([
    { name: "sessionid", value: session.sessionid, url: baseURL, httpOnly: true, sameSite: "Lax" },
  ]);
}
async function setGuestCart(page: Page, variantSizeId: number) {
  await page.goto("/fa");
  await page.evaluate((id) => {
    localStorage.setItem("vedzmani.guest-cart.v1", JSON.stringify({
      token: "54f7ac3d-09a8-46ba-ae19-e55f4c26a0f1",
      items: [{
        variant_size_id: id,
        quantity: 2,
        product: { id: 1, name: "تی‌شرت تست", slug: "e2e-tee-02" },
        color: { name: "مشکی", slug: "black", hex_color: "#000000" },
        variant_size: { id, sku: "e2e-tee-02-black-m", label: "M" },
        unit_price: "1000",
        image: null,
      }],
    }));
  }, variantSizeId);
}

test.describe("guest cart and payment-safe checkout", () => {
  test("guest can add a product from its detail page without an account", async ({ page }) => {
    test.skip(!backendDir, "E2E_BACKEND_DIR not set");
    await page.goto("/fa/products/e2e-tee-02");
    await page.getByRole("radio", { name: "M" }).check();
    await page.getByRole("button", { name: "افزودن به سبد خرید" }).click();
    await expect(page.getByText("به سبد خرید اضافه شد.")).toBeVisible();
    const guestLine = await page.evaluate(() => {
      const cart = JSON.parse(localStorage.getItem("vedzmani.guest-cart.v1") || "{}");
      return cart.items?.[0];
    });
    expect(guestLine.quantity).toBe(1);
    expect(guestLine.variant_size.sku).toBe("e2e-tee-02-black-m");
    await expect(page.getByRole("link", { name: "سبد خرید، ۱ کالا" })).toBeVisible();
  });

  test("anonymous direct checkout asks for sign-in or account creation and never posts an order", async ({ page }) => {
    let orderPosts = 0;
    page.on("request", (request) => {
      if (request.url().includes("/api/orders/") && request.method() === "POST") orderPosts += 1;
    });
    await page.goto("/fa/checkout");
    await expect(page.getByRole("heading", { name: "برای ادامه وارد شوید یا حساب بسازید" })).toBeVisible();
    await expect(page.getByRole("link", { name: "ورود / ساخت حساب" })).toHaveAttribute("href", /\/fa\/sign-in\?next=/);
    expect(orderPosts).toBe(0);
  });

  test("guest cart is editable and checkout CTA sends the visitor to the OTP account flow", async ({ page }) => {
    test.skip(!backendDir, "E2E_BACKEND_DIR not set");
    const session = await createSession(); // get a real seeded variant ID, but do not set its session cookie
    await setGuestCart(page, session.variantSizeIds["e2e-tee-02-black-m"]);
    await page.goto("/fa/cart");
    await expect(page.getByTestId("guest-cart-line")).toBeVisible();
    await expect(page.getByRole("link", { name: "تکمیل خرید" })).toHaveAttribute("href", /\/fa\/sign-in\?next=/);
    await page.getByRole("button", { name: "افزایش تعداد تی‌شرت تست" }).click();
    const guestLine = await page.evaluate(() => {
      const cart = JSON.parse(localStorage.getItem("vedzmani.guest-cart.v1") || "{}");
      return cart.items?.[0];
    });
    expect(guestLine.quantity).toBe(3);
    await expect(page.getByRole("link", { name: "تکمیل خرید" })).toBeVisible();
  });

  test("authenticated customer gets the guest cart merged once and sees delivery details without an order action", async ({ page, baseURL }) => {
    test.skip(!backendDir, "E2E_BACKEND_DIR not set");
    const session = await createSession();
    await applySession(page, session, baseURL!);
    await setGuestCart(page, session.variantSizeIds["e2e-tee-02-black-m"]);
    let merges = 0;
    let orderPosts = 0;
    page.on("request", (request) => {
      if (request.url().endsWith("/api/cart/merge-guest/") && request.method() === "POST") merges += 1;
      if (request.url().includes("/api/orders/") && request.method() === "POST") orderPosts += 1;
    });

    await page.goto("/fa/checkout");
    await expect(page.getByRole("heading", { name: "اطلاعات تحویل" })).toBeVisible();
    await expect(page.getByText("Tee 02")).toBeVisible();
    await expect(page.getByLabel("نام گیرنده")).toBeVisible();
    await expect(page.getByText(/ثبت سفارش و پرداخت هنوز فعال نشده‌اند/)).toBeVisible();
    await expect(page.getByRole("button", { name: "ثبت سفارش" })).toHaveCount(0);
    expect(merges).toBe(1);
    expect(orderPosts).toBe(0);

    const cart = await page.request.get("/api/cart/");
    expect(cart.status()).toBe(200);
    expect((await cart.json()).items[0].quantity).toBe(2);

    await page.reload();
    await expect(page.getByRole("heading", { name: "اطلاعات تحویل" })).toBeVisible();
    expect(merges).toBe(1);
    expect(orderPosts).toBe(0);
  });
});
