import { expect, test, type Page } from "@playwright/test";

const cards = (page: Page) => page.locator('a[href^="/fa/products/e2e-"]');
const noHorizontalOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test.describe("کاتالوگ دسکتاپ", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("همه محصولات منتشرشده با صفحه‌بندی نمایش داده می‌شوند", async ({ page }) => {
    await page.goto("/fa/products");
    await expect(page.getByRole("heading", { level: 1, name: "همه محصولات" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "۳۰ محصول" })).toBeVisible();
    await expect(cards(page)).toHaveCount(24);
    await expect(page.getByText("صفحه ۱ از ۲")).toBeVisible();
  });

  test("منوی کشویی دسته‌بندی دسکتاپ به صفحه همان دسته می‌رود", async ({ page }) => {
    await page.goto("/fa");
    const nav = page.getByRole("navigation", { name: "ناوبری اصلی" });
    await nav.locator("summary").filter({ hasText: "دسته‌بندی‌ها" }).click();
    await nav.getByRole("link", { name: "هودی" }).click();
    await expect(page).toHaveURL(/\/fa\/categories\/hoodies$/);
    await expect(page.getByRole("heading", { level: 1, name: "هودی" })).toBeVisible();
  });
  test("دسته‌بندی بافت از منوی دسکتاپ قابل دسترسی است", async ({ page }) => {
    await page.goto("/fa");
    const nav = page.getByRole("navigation", { name: "ناوبری اصلی" });
    await nav.locator("summary").filter({ hasText: "دسته‌بندی‌ها" }).click();
    await nav.getByRole("link", { name: "بافت" }).click();
    await expect(page).toHaveURL(/\\/fa\\/categories\\/knitwear$/);
    await expect(page.getByRole("heading", { level: 1, name: "بافت" })).toBeVisible();
  });

  test("جست‌وجو با کد محصول و نام از آیکون هدر انجام می‌شود", async ({ page }) => {
    await page.goto("/fa/products");
    await page.getByRole("button", { name: "جستجوی محصولات" }).click();
    const dialog = page.getByRole("dialog");
    const input = dialog.getByRole("textbox", { name: "نام یا کد محصول" });
    await input.fill("E2E-HOODIE-07");
    const result = dialog.getByRole("button", { name: /کد: E2E-HOODIE-07/ });
    await expect(result).toContainText("Hoodie 07");
    await input.press("Enter");
    await expect(page).toHaveURL(/search=E2E-HOODIE-07/);
    await expect(cards(page)).toHaveCount(1);
  });

  test("انتخاب نتیجه جست‌وجو و سابقه جست‌وجو کار می‌کند", async ({ page }) => {
    await page.goto("/fa");
    await page.getByRole("button", { name: "جستجوی محصولات" }).click();
    const dialog = page.getByRole("dialog");
    const input = dialog.getByRole("textbox", { name: "نام یا کد محصول" });
    await input.fill("Hoodie 07");
    const result = dialog.getByRole("button", { name: /Hoodie 07/ });
    await expect(result).toBeVisible();
    await result.click();
    await expect(page).toHaveURL(/\/fa\/products\/e2e-hoodie-07$/);
    await page.getByRole("button", { name: "جستجوی محصولات" }).click();
    await expect(page.getByText("جستجوهای اخیر")).toBeVisible();
    await expect(page.getByRole("button", { name: "Hoodie 07" })).toBeVisible();
  });

  test("دسته‌بندی و فیلتر موجودی نتایج را محدود می‌کنند", async ({ page }) => {
    await page.goto("/fa");
    await page.getByRole("button", { name: "باز کردن منو" }).click();
    const menu = page.getByRole("dialog");
    await menu.locator("summary").filter({ hasText: "دسته‌بندی‌ها" }).click();
    await menu.getByRole("link", { name: "تی شرت" }).click();
    await expect(page).toHaveURL(/\/fa\/categories\/t-shirts$/);
    await expect(page.getByRole("heading", { level: 1, name: "تی شرت" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "۱۵ محصول" })).toBeVisible();

    await page.goto("/fa/products?category=hoodies");
    await page.getByRole("checkbox", { name: "فقط کالاهای موجود" }).check();
    await page.getByRole("button", { name: "اعمال فیلترها" }).click();
    await expect(page).toHaveURL(/in_stock=true/);
    await expect(page.getByRole("heading", { level: 2, name: "۱۴ محصول" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "هودی" })).toBeChecked();
  });

  test("فیلتر بازه قیمت در سمت سرور اعمال می‌شود", async ({ page }) => {
    await page.goto("/fa/products?min_price=14000&max_price=15500");
    await expect(page.getByLabel("حداقل قیمت")).toHaveValue("14000");
    await expect(cards(page)).toHaveCount(4);
  });

  test("مرتب‌سازی با لینک‌ها اعمال می‌شود", async ({ page }) => {
    await page.goto("/fa/products");
    await expect(page.getByRole("link", { name: "نام (الف تا ی)" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "نام (ی تا الف)" })).toHaveCount(0);
    await page.getByRole("link", { name: "ارزان‌ترین" }).click();
    await expect(page).toHaveURL(/sort=price_asc/);
    await expect(cards(page).first().getByRole("heading")).toHaveText("Tee 01");
    await page.getByRole("link", { name: "گران‌ترین" }).click();
    await expect(page).toHaveURL(/sort=price_desc/);
    await expect(cards(page).first().getByRole("heading")).toHaveText("Hoodie 15");
    await expect(page.getByRole("link", { name: "گران‌ترین" })).toHaveAttribute("aria-current", "true");
  });

  test("صفحه‌بندی وضعیت فیلتر را حفظ می‌کند", async ({ page }) => {
    await page.goto("/fa/products?sort=price_asc");
    await expect(page.getByText("صفحه ۱ از ۲")).toBeVisible();
    await page.getByRole("link", { name: "بعدی" }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(page).toHaveURL(/sort=price_asc/);
    await expect(page.getByText("صفحه ۲ از ۲")).toBeVisible();
    await expect(cards(page)).toHaveCount(6);
    await page.goBack();
    await expect(page.getByText("صفحه ۱ از ۲")).toBeVisible();
  });

  test("صفحه خارج از محدوده به صفحه اول برمی‌گردد", async ({ page }) => {
    await page.goto("/fa/products?page=99");
    await expect(page).toHaveURL(/\/fa\/products$/);
    await expect(cards(page)).toHaveCount(24);
  });

  test("جست‌وجوی بدون نتیجه راه پاک‌کردن فیلتر را نمایش می‌دهد", async ({ page }) => {
    await page.goto("/fa/products?search=zzzznothing");
    await expect(page.getByText("محصولی پیدا نشد")).toBeVisible();
    await page.getByRole("link", { name: "پاک کردن جستجو و فیلترها" }).click();
    await expect(page).toHaveURL(/\/fa\/products$/);
    await expect(page.getByRole("heading", { level: 2, name: "۳۰ محصول" })).toBeVisible();
  });

  test("صفحه محصول، رنگ و موجودی سایزها را نشان می‌دهد", async ({ page }) => {
    await page.goto("/fa/products/e2e-hoodie-01");
    await expect(page.getByRole("heading", { level: 1, name: "Hoodie 01" })).toBeVisible();
    await expect(page.getByText("Fixture Hoodie number 1.")).toBeVisible();
    await expect(page.getByText("موجود", { exact: true })).toBeVisible();
    await expect(page.getByText("M : 5")).toBeVisible();
    await expect(page.getByText(/تومان/)).toBeVisible();
    await expect(page.getByRole("button", { name: "افزودن به سبد خرید" })).toBeEnabled();
    await expect(page.getByRole("radio", { name: "M" })).toBeEnabled();

    await page.locator("label").filter({ has: page.getByRole("radio", { name: "M" }) }).click();
    const mTable = page.getByRole("table", { name: "اندازه‌های سایز M" });
    await expect(mTable).toBeVisible();
    await expect(mTable).toContainText("56 سانتی‌متر");
    await expect(mTable).toContainText("64 سانتی‌متر");
    await page.locator("label").filter({ has: page.getByRole("radio", { name: "L" }) }).click();
    const lTable = page.getByRole("table", { name: "اندازه‌های سایز L" });
    await expect(lTable).toBeVisible();
    await expect(lTable).toContainText("59 سانتی‌متر");
    await expect(lTable).not.toContainText("56 سانتی‌متر");

    const gallery = page.getByRole("region", { name: "تصاویر محصول" });
    const mainImage = gallery.getByRole("img");
    await expect(mainImage).toHaveAttribute("alt", "Hoodie 01 Black front");
    await gallery.getByRole("button", { name: "تصویر بعدی" }).click();
    await expect(mainImage).toHaveAttribute("alt", "Hoodie 01 Black detail");

    await page.getByRole("link", { name: "White" }).click();
    await expect(page).toHaveURL(/color=white/);
    await expect(mainImage).toHaveAttribute("alt", "Hoodie 01 White front");
    await expect(page.getByText("ناموجود", { exact: true })).toBeVisible();
    await expect(page.getByText("M : 0").locator("..")).toHaveClass(/border-red-500/);
    await expect(page.getByRole("radio", { name: "M" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "افزودن به سبد خرید" })).toBeDisabled();
    await page.getByRole("link", { name: "بازگشت به محصولات" }).click();
    await expect(page).toHaveURL(/\/fa\/products$/);
  });

  test("قیمت تخفیف‌خورده فقط در صورت وجود نشان داده می‌شود", async ({ page }) => {
    await page.goto("/fa/products/e2e-hoodie-02");
    await expect(page.locator("del")).toHaveCount(1);
    await page.goto("/fa/products/e2e-hoodie-04");
    await expect(page.locator("del")).toHaveCount(0);
  });

  test("محصول ناشناخته 404 است", async ({ page }) => {
    const response = await page.goto("/fa/products/does-not-exist");
    expect(response?.status()).toBe(404);
  });
});

test.describe("کاتالوگ موبایل", () => {
  test.use({ viewport: { width: 375, height: 800 } });

  test("دسته‌بندی بافت از منوی موبایل قابل دسترسی است", async ({ page }) => {
    await page.goto("/fa");
    await page.getByRole("button", { name: "باز کردن منو" }).click();
    const menu = page.getByRole("dialog");
    await menu.locator("summary").filter({ hasText: "دسته‌بندی‌ها" }).click();
    await menu.getByRole("link", { name: "بافت" }).click();
    await expect(page).toHaveURL(/\\/fa\\/categories\\/knitwear$/);
    await expect(page.getByRole("heading", { level: 1, name: "بافت" })).toBeVisible();
  });

  test("فیلترها در دیالوگ باز می‌شوند و صفحه اسکرول افقی ندارد", async ({ page }) => {
    await page.goto("/fa/products");
    expect(await noHorizontalOverflow(page)).toBe(true);
    const dialog = page.getByRole("dialog", { name: "فیلترها" });
    await expect(dialog).toBeHidden();
    await page.getByRole("button", { name: "فیلترها" }).click();
    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await page.getByRole("button", { name: "فیلترها" }).click();
    await dialog.getByRole("checkbox", { name: "تی شرت" }).check();
    await dialog.getByRole("button", { name: "اعمال فیلترها" }).click();
    await expect(page).toHaveURL(/category=t-shirts/);
    await expect(page.getByRole("heading", { level: 2, name: "۱۵ محصول" })).toBeVisible();
    await expect(dialog).toBeHidden();
  });

  test("صفحه جزئیات محصول در موبایل سرریز افقی ندارد", async ({ page }) => {
    await page.goto("/fa/products/e2e-hoodie-01");
    await expect(page.getByRole("heading", { level: 1, name: "Hoodie 01" })).toBeVisible();
    expect(await noHorizontalOverflow(page)).toBe(true);
  });
});
