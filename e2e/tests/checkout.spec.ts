import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Checkout e2e. Runs against the real stack (Nginx -> Next + Django + PostgreSQL), like the
 * other specs, but needs a THROWAWAY database seeded with e2e/seed_catalog.py.
 *
 * Required env for everything except the anonymous test:
 *   E2E_BACKEND_DIR  absolute path to /backend (same DATABASE_URL/REDIS_URL as the running server)
 *   E2E_PYTHON       python that has the backend requirements (default: "python")
 *
 * Sign-in: production login needs an SMS provider that does not exist yet, so tests cannot
 * complete the OTP flow. e2e_helper.py creates a REAL Django session for a test user via
 * Django's own `force_login`; the browser then uses it as a normal login cookie. Carts are
 * filled through the real cart API, and CSRF, validation, stock and order creation are all real.
 * Tests named "(mocked response)" intercept the order POST to exercise failure states that
 * cannot be produced on demand; they assert UI behavior only.
 */

const backendDir = process.env.E2E_BACKEND_DIR;
const python = process.env.E2E_PYTHON ?? "python";
const helperPath = path.join(__dirname, "..", "e2e_helper.py");

type Session = { sessionid: string; phone: string; variantSizeIds: Record<string, number> };

function helper<T>(env: Record<string, string>): T {
  if (!backendDir) throw new Error("E2E_BACKEND_DIR is required for tests that sign in");
  // `shell -c exec(...)` rather than piping stdin: piped stdin is not executed on Windows.
  const out = execFileSync(
    python,
    ["manage.py", "shell", "-c", `exec(open(${JSON.stringify(helperPath)}, encoding="utf-8").read())`],
    { cwd: backendDir, env: { ...process.env, ...env }, encoding: "utf8" },
  );
  const line = out.split(/\r?\n/).find((l) => l.startsWith("E2E_JSON:"));
  if (!line) throw new Error(`helper produced no result:\n${out}`);
  return JSON.parse(line.slice("E2E_JSON:".length)) as T;
}

let counter = 0;
function uniquePhone(): string {
  counter += 1;
  const tail = String(Date.now() % 1_000_000).padStart(6, "0");
  return `0912${tail}${counter % 10}`;
}

async function signIn(page: Page, baseURL: string): Promise<Session> {
  const session = helper<Session>({ E2E_ACTION: "session", E2E_PHONE: uniquePhone() });
  await page.context().addCookies([
    { name: "sessionid", value: session.sessionid, url: baseURL, httpOnly: true, sameSite: "Lax" },
  ]);
  return session;
}

async function csrf(page: Page): Promise<string> {
  const res = await page.request.get("/api/auth/csrf/");
  return (await res.json()).csrfToken as string;
}

async function addToCart(page: Page, variantSizeId: number, quantity: number) {
  const res = await page.request.post("/api/cart/items/", {
    data: { variant_size_id: variantSizeId, quantity },
    headers: { "X-CSRFToken": await csrf(page) },
  });
  expect(res.status(), await res.text()).toBe(201);
}

const getJson = async (page: Page, url: string) => (await page.request.get(url)).json();
const money = (value: string) => new Intl.NumberFormat("fa-IR").format(Number(value));

const DELIVERY = {
  "نام گیرنده": "Sara Ahmadi",
  استان: "Tehran",
  شهر: "Tehran",
  نشانی: "Valiasr St, No. 12",
  "کد پستی": "1234567890",
};

async function fillDelivery(page: Page, values: Record<string, string> = DELIVERY) {
  for (const [label, value] of Object.entries(values)) await page.getByLabel(label).fill(value);
}

const placeOrder = (page: Page) => page.getByRole("button", { name: "ثبت سفارش" });

test.describe("checkout", () => {
  test.skip(({}, testInfo) => !backendDir && testInfo.title !== ANON, "E2E_BACKEND_DIR not set");

  const ANON = "anonymous visitor is asked to sign in and no form or order request is made";
  test(ANON, async ({ page }) => {
    let orderRequests = 0;
    page.on("request", (r) => r.url().includes("/api/orders/") && orderRequests++);
    await page.goto("/fa/checkout");
    await expect(page.getByRole("heading", { name: "برای ادامه وارد شوید" })).toBeVisible();
    await expect(placeOrder(page)).toHaveCount(0);
    expect(orderRequests).toBe(0);
  });

  test("signed-in customer with an empty cart sees the empty state", async ({ page, baseURL }) => {
    await signIn(page, baseURL!);
    await page.goto("/fa/checkout");
    await expect(page.getByRole("heading", { name: "سبد خرید شما خالی است" })).toBeVisible();
    await expect(page.getByRole("link", { name: "مشاهده محصولات" })).toHaveAttribute("href", "/fa/products");
    await expect(placeOrder(page)).toHaveCount(0);
  });

  test("client validation blocks an invalid submit without any order request", async ({ page, baseURL }) => {
    const s = await signIn(page, baseURL!);
    await addToCart(page, s.variantSizeIds["e2e-tee-02-black-m"], 1);
    let posts = 0;
    page.on("request", (r) => r.url().includes("/api/orders/") && r.method() === "POST" && posts++);

    await page.goto("/fa/checkout");
    await placeOrder(page).click();
    await expect(page.getByText("این فیلد الزامی است.")).toHaveCount(5);
    await expect(page.getByLabel("نام گیرنده")).toBeFocused();

    await fillDelivery(page, { ...DELIVERY, "کد پستی": "123" });
    await placeOrder(page).click();
    await expect(page.getByText("کد پستی ۱۰ رقمی وارد کنید.")).toBeVisible();
    expect(posts).toBe(0);
    expect((await getJson(page, "/api/cart/")).items).toHaveLength(1);
    expect(await getJson(page, "/api/orders/")).toHaveLength(0);
  });

  test("places an order and shows the confirmation Django returned", async ({ page, baseURL }) => {
    const s = await signIn(page, baseURL!);
    await addToCart(page, s.variantSizeIds["e2e-hoodie-02-black-m"], 2);
    await addToCart(page, s.variantSizeIds["e2e-tee-04-black-m"], 1);
    const cart = await getJson(page, "/api/cart/");

    await page.goto("/fa/checkout");
    await expect(page.getByTestId("cart-total")).toHaveText(money(cart.total));

    await fillDelivery(page, { ...DELIVERY, "کد پستی": "۱۲۳۴۵۶۷۸۹۰" }); // Persian digits
    const posted = page.waitForRequest((r) => r.url().endsWith("/api/orders/") && r.method() === "POST");
    await placeOrder(page).click();

    const request = await posted;
    // Only the five documented delivery fields are sent: no user, items, prices, status or total.
    expect(Object.keys(request.postDataJSON()).sort()).toEqual(
      ["address", "city", "postal_code", "province", "recipient_name"],
    );
    expect(request.headers()["x-csrftoken"]).toBeTruthy();

    await expect(page.getByRole("heading", { name: "سفارش ثبت شد" })).toBeVisible();
    const orders = await getJson(page, "/api/orders/");
    expect(orders).toHaveLength(1);
    await expect(page.getByTestId("order-id")).toHaveText(String(orders[0].id));
    await expect(page.getByTestId("order-total")).toHaveText(money(orders[0].total));
    expect(orders[0].payment_status).toBe("unpaid");
    await expect(page.getByText("پرداخت نشده. هیچ مبلغی دریافت نشده است.")).toBeVisible();
    await expect(page.getByText("هزینه ارسال شامل نمی‌شود").first()).toBeVisible();
    await expect(page.getByText("Sara Ahmadi")).toBeVisible();
    expect((await getJson(page, "/api/cart/")).items).toHaveLength(0); // cleared by Django, not by the UI
  });

  test("a double click creates exactly one order", async ({ page, baseURL }) => {
    const s = await signIn(page, baseURL!);
    await addToCart(page, s.variantSizeIds["e2e-hoodie-04-black-m"], 1);
    let posts = 0;
    await page.route("**/api/orders/", async (route) => {
      if (route.request().method() === "POST") {
        posts += 1;
        await new Promise((resolve) => setTimeout(resolve, 1500)); // keep the first request in flight
      }
      await route.continue();
    });

    await page.goto("/fa/checkout");
    await fillDelivery(page);
    await placeOrder(page).dblclick();
    await page.getByLabel("کد پستی").press("Enter"); // a third attempt while still in flight
    await expect(page.getByRole("heading", { name: "سفارش ثبت شد" })).toBeVisible();
    expect(posts).toBe(1);
    expect(await getJson(page, "/api/orders/")).toHaveLength(1);
  });

  test("submitting a stale page after the cart was already ordered does not blindly re-order", async ({
    page,
    baseURL,
  }) => {
    const s = await signIn(page, baseURL!);
    await addToCart(page, s.variantSizeIds["e2e-hoodie-05-black-m"], 1);
    await page.goto("/fa/checkout");
    await fillDelivery(page);

    // The order is placed elsewhere (another tab/device) while this page is still open.
    const other = await page.request.post("/api/orders/", {
      data: { recipient_name: "A", province: "B", city: "C", address: "D", postal_code: "1234567890" },
      headers: { "X-CSRFToken": await csrf(page) },
    });
    expect(other.status()).toBe(201);

    await placeOrder(page).click();
    await expect(page.getByRole("heading", { name: "پیش از سفارش مجدد بررسی کنید" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "سفارش ثبت شد" })).toHaveCount(0);
    expect(await getJson(page, "/api/orders/")).toHaveLength(1);
  });

  test("insufficient stock at submit: order rejected, form values kept, cart refreshed", async ({
    page,
    baseURL,
  }) => {
    const s = await signIn(page, baseURL!);
    const sku = "e2e-tee-06-black-m";
    await addToCart(page, s.variantSizeIds[sku], 3);
    await page.goto("/fa/checkout");
    await fillDelivery(page);

    helper({ E2E_ACTION: "set_stock", E2E_SKU: sku, E2E_STOCK: "1" }); // stock drops after carting
    await placeOrder(page).click();

    await expect(page.getByText("موجودی یک یا چند کالا کافی نیست.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "سفارش ثبت شد" })).toHaveCount(0);
    await expect(page.getByLabel("نام گیرنده")).toHaveValue(DELIVERY["نام گیرنده"]);
    await expect(page.getByLabel("نشانی")).toHaveValue(DELIVERY.نشانی);
    await expect(page.getByText("موجودی کافی نیست").first()).toBeVisible(); // refreshed cart line
    expect(await getJson(page, "/api/orders/")).toHaveLength(0);
    expect((await getJson(page, "/api/cart/")).items).toHaveLength(1);
  });

  for (const failure of ["server error", "network failure"] as const) {
    test(`unconfirmed outcome on ${failure} (mocked response): no success shown, values kept, retry works`, async ({
      page,
      baseURL,
    }) => {
      const s = await signIn(page, baseURL!);
      await addToCart(page, s.variantSizeIds["e2e-hoodie-06-black-m"], 1);
      const handler = (route: import("@playwright/test").Route) =>
        route.request().method() === "POST"
          ? failure === "server error"
            ? route.fulfill({
                status: 500,
                contentType: "application/json",
                body: JSON.stringify({ error: { code: "error", message: "boom" } }),
              })
            : route.abort("failed")
          : route.continue();
      await page.route("**/api/orders/", handler);

      await page.goto("/fa/checkout");
      await fillDelivery(page);
      await placeOrder(page).click();

      await expect(page.getByText("نتوانستیم تأیید کنیم که سفارش ثبت شده است یا نه.")).toBeVisible();
      await expect(page.getByRole("heading", { name: "سفارش ثبت شد" })).toHaveCount(0);
      await expect(page.getByLabel("شهر")).toHaveValue("Tehran");
      await expect(placeOrder(page)).toBeEnabled();

      await page.unroute("**/api/orders/", handler); // connection recovers: the customer retries
      await placeOrder(page).click();
      await expect(page.getByRole("heading", { name: "سفارش ثبت شد" })).toBeVisible();
      expect(await getJson(page, "/api/orders/")).toHaveLength(1);
    });
  }

  test("Persian locale renders RTL and completes an order", async ({ page, baseURL }) => {
    const s = await signIn(page, baseURL!);
    await addToCart(page, s.variantSizeIds["e2e-tee-08-black-m"], 1);
    await page.goto("/fa/checkout");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { name: "تسویه حساب", level: 1 })).toBeVisible();

    await page.getByLabel("نام گیرنده").fill("سارا احمدی");
    await page.getByLabel("استان").fill("تهران");
    await page.getByLabel("شهر").fill("تهران");
    await page.getByLabel("نشانی").fill("خیابان ولیعصر، پلاک ۱۲");
    await page.getByLabel("کد پستی").fill("1234567890");
    await page.getByRole("button", { name: "ثبت سفارش" }).click();

    await expect(page.getByRole("heading", { name: "سفارش ثبت شد" })).toBeVisible();
    await expect(page.getByText("پرداخت نشده. هیچ مبلغی دریافت نشده است.")).toBeVisible();
    expect(await getJson(page, "/api/orders/")).toHaveLength(1);
  });
});
