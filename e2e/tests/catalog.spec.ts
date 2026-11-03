import { expect, test, type Page } from "@playwright/test";

const cards = (page: Page) => page.locator('a[href^="/fa/products/e2e-"]');
const noHorizontalOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test.describe("کاتالوگ دسکتاپ", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("همه محصولات منتشرشده با صفحه‌بندی نمایش داده می‌شوند", async ({ page }) => {
    await page.goto("/fa/products");
    await expect(page.getByRole("heading", { level: 1, name: "همه محصولات" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "۶۰ محصول" })).toBeVisible();
    await expect(cards(page)).toHaveCount(24);
    await expect(page.getByText("صفحه ۱ از ۳")).toBeVisible();
  });

  test("هر رنگ در فهرست کارت مستقل با تصویر همان رنگ دارد", async ({ page }) => {
    await page.goto("/fa/products?search=E2E-HOODIE-01");
    const blackCard = page.locator('a[href="/fa/products/e2e-hoodie-01/black"]');
    const whiteCard = page.locator('a[href="/fa/products/e2e-hoodie-01/white"]');
    await expect(blackCard).toBeVisible();
    await expect(whiteCard).toBeVisible();
    await expect(blackCard.getByRole("img")).toHaveAttribute("alt", "Hoodie 01 Black front");
    await expect(whiteCard.getByRole("img")).toHaveAttribute("alt", "Hoodie 01 White front");
    await expect(blackCard).toContainText("Black");
    await expect(whiteCard).toContainText("White");
    const blackCode = await blackCard.locator("p").filter({ hasText: "کد محصول:" }).textContent();
    const whiteCode = await whiteCard.locator("p").filter({ hasText: "کد محصول:" }).textContent();
    expect(blackCode).toMatch(/کد محصول:\s*\d+/);
    expect(whiteCode).toMatch(/کد محصول:\s*\d+/);
    const blackNumericCode = blackCode?.match(/کد محصول:\s*(\d+)/)?.[1];
    const whiteNumericCode = whiteCode?.match(/کد محصول:\s*(\d+)/)?.[1];
    expect(blackNumericCode).toBeTruthy();
    expect(whiteNumericCode).toBeTruthy();
    expect(blackNumericCode).not.toEqual(whiteNumericCode);
  });

  test("فیلتر دسکتاپ به‌صورت سایدبار ثابت می‌ماند، حتی پس از ناوبری فیلتر", async ({ page }) => {
    await page.goto("/fa/products");
    const sidebar = page.locator('div[aria-label="فیلترها"]');
    await expect(sidebar).toBeVisible();
    await expect(page.locator('dialog[aria-label="فیلترها"]')).toBeHidden();

    await page.goto("/fa/products?category=hoodies&filters_open=1");
    await expect(sidebar).toBeVisible();
    await expect(page.locator('dialog[aria-label="فیلترها"]')).toBeHidden();
    await expect(page.getByRole("checkbox", { name: "هودی" })).toBeChecked();
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
    await expect(page).toHaveURL(/\/fa\/categories\/knitwear$/);
    await expect(page.getByRole("heading", { level: 1, name: "بافت" })).toBeVisible();
  });

  test("جست‌وجو با کد عددی کارت رنگ از آیکون هدر انجام می‌شود", async ({ page }) => {
    await page.goto("/fa/products?search=Hoodie%2007");
    const blackCard = page.locator('a[href="/fa/products/e2e-hoodie-07/black"]');
    await expect(blackCard).toBeVisible();
    const cardCode = await blackCard.locator("p").filter({ hasText: "کد محصول:" }).textContent();
    const numericCode = cardCode?.match(/کد محصول:\s*(\d+)/)?.[1];
    expect(numericCode).toBeTruthy();

    await page.getByRole("button", { name: "جستجوی محصولات" }).click();
    const input = page.getByRole("searchbox", { name: "جستجوی نام یا کد محصول" });
    await input.fill(numericCode!);
    const result = page.locator("#navbar-search-results").getByRole("button", { name: new RegExp(`کد: ${numericCode}`) }).first();
    await expect(result).toContainText("Hoodie 07");
    await input.press("Enter");
    await expect(page).toHaveURL(new RegExp(`search=${numericCode}`));
    await expect(cards(page)).toHaveCount(1);
  });

  test("انتخاب نتیجه جست‌وجو و سابقه جست‌وجو کار می‌کند", async ({ page }) => {
    await page.goto("/fa");
    await page.getByRole("button", { name: "جستجوی محصولات" }).click();
    const input = page.getByRole("searchbox", { name: "جستجوی نام یا کد محصول" });
    await input.fill("Hoodie 07");
    const result = page.locator("#navbar-search-results").getByRole("button", { name: /Hoodie 07/ }).first();
    await expect(result).toBeVisible();
    await result.click();
    await expect(page).toHaveURL(/\/fa\/products\/e2e-hoodie-07\/black$/);
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
    await expect(page.getByRole("heading", { level: 2, name: "۳۰ محصول" })).toBeVisible();

    await page.goto("/fa/products?category=hoodies");
    await page.getByRole("checkbox", { name: "فقط کالاهای موجود" }).check();
    await page.getByRole("button", { name: /اعمال فیلترها/ }).click();
    await expect(page).toHaveURL(/in_stock=true/);
    await expect(page.getByRole("heading", { level: 2, name: "۲۷ محصول" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "هودی" })).toBeChecked();
  });



  test("انتخاب دسته‌بندی فقط جزئیات فیلتر را باز می‌کند و نتایج با اعمال فیلتر تغییر می‌کنند", async ({ page }) => {
    await page.goto("/fa/products");
    await page.getByRole("checkbox", { name: "هودی" }).check();
    await expect(page).toHaveURL(/draft_category=hoodies/);
    await expect(page).toHaveURL(/filter_preview=1/);
    await expect(page.getByRole("heading", { level: 2, name: "۶۰ محصول" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "هودی" })).toBeChecked();
    await expect(page.getByRole("group", { name: "کالکشن" })).toContainText("Winter");
    await expect(page.getByRole("group", { name: "رنگ" })).toContainText("Black");
    await expect(page.getByRole("group", { name: "سایز" })).toContainText("M");
    await expect(page.getByRole("button", { name: "اعمال فیلترها (۳۰)" })).toBeVisible();

    await page.getByRole("button", { name: /اعمال فیلترها/ }).click();
    await expect(page).toHaveURL(/category=hoodies/);
    await expect(page).not.toHaveURL(/draft_category=/);
    await expect(page).not.toHaveURL(/filter_preview=1/);
    await expect(page.locator('a[href^="/fa/products/e2e-hoodie-"]')).toHaveCount(24);
    await expect(page.locator('a[href^="/fa/products/e2e-tee-"]')).toHaveCount(0);
  });

  test("پاک کردن همه فیلترها تمام وضعیت URL و فرم را پاک می‌کند", async ({ page }) => {
    await page.goto("/fa/products?search=Hoodie&category=hoodies&color=black&size=m&min_price=1000&max_price=50000&in_stock=true&sort=price_asc");
    await expect(page.getByRole("checkbox", { name: "هودی" })).toBeChecked();
    await page.getByRole("link", { name: "حذف همه فیلترها" }).click();
    await expect(page).toHaveURL(/\/fa\/products\?filters_open=1$/);
    await expect(page.getByRole("checkbox", { name: "هودی" })).not.toBeChecked();
    await expect(page.getByRole("link", { name: "ارزان‌ترین" })).not.toHaveAttribute("aria-current", "true");
  });

  test("فیلتر بازه قیمت در سمت سرور اعمال می‌شود", async ({ page }) => {
    await page.goto("/fa/products?category=hoodies&min_price=14000&max_price=15500");
    const sidebar = page.locator('div[aria-label="فیلترها"]');
    await expect(sidebar.getByLabel("حداقل قیمت")).toHaveValue("14000");
    await expect(sidebar.getByTestId("price-range-control").locator('input[type="range"]')).toHaveCount(2);
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
    await expect(page.getByText("صفحه ۱ از ۳")).toBeVisible();
    await page.getByRole("link", { name: "بعدی" }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(page).toHaveURL(/sort=price_asc/);
    await expect(page.getByText("صفحه ۲ از ۳")).toBeVisible();
    await expect(cards(page)).toHaveCount(24);
    await page.goBack();
    await expect(page.getByText("صفحه ۱ از ۳")).toBeVisible();
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
    await expect(page.getByRole("heading", { level: 2, name: "۶۰ محصول" })).toBeVisible();
  });

  test("صفحه محصول، رنگ و موجودی سایزها را نشان می‌دهد", async ({ page }) => {
    await page.goto("/fa/products/e2e-hoodie-01");
    await expect(page.getByRole("heading", { level: 1, name: "Hoodie 01" })).toBeVisible();
    await expect(page.getByText("Fixture Hoodie number 1.")).toBeVisible();
    await expect(page.getByText("موجود", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("M : 5")).toBeVisible();
    await expect(page.getByText(/تومان/).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "افزودن به سبد خرید" })).toBeEnabled();
    await expect(page.getByRole("radio", { name: "M" })).toBeEnabled();

    await page.locator("label").filter({ has: page.getByRole("radio", { name: "M" }) }).click();
    const mTable = page.getByRole("table", { name: "اندازه‌های سایز M" });
    await expect(mTable).toBeVisible();
    await expect(mTable).toContainText("56 سانتی‌متر");
    await expect(mTable).toContainText("64 سانتی‌متر");
    await expect(page.getByText("توضیح اختصاصی رنگ مشکی و سایز M", { exact: true })).toBeVisible();
    await page.locator("label").filter({ has: page.getByRole("radio", { name: "L" }) }).click();
    const lTable = page.getByRole("table", { name: "اندازه‌های سایز L" });
    await expect(lTable).toBeVisible();
    await expect(lTable).toContainText("59 سانتی‌متر");
    await expect(lTable).not.toContainText("56 سانتی‌متر");
    await expect(page.getByText("توضیح مشترک سایز L", { exact: true })).toBeVisible();

    const gallery = page.getByRole("region", { name: "تصاویر محصول" });
    const mainImage = gallery.getByRole("img");
    await expect(mainImage).toHaveAttribute("alt", "Hoodie 01 Black front");
    await gallery.getByRole("button", { name: "تصویر بعدی" }).click();
    await expect(mainImage).toHaveAttribute("alt", "Hoodie 01 Black detail");

    await page.getByRole("link", { name: "انتخاب رنگ White" }).click();
    await expect(page).toHaveURL(/color=white/);
    await expect(mainImage).toHaveAttribute("alt", "Hoodie 01 White front");
    await expect(page.getByText("ناموجود", { exact: true })).toBeVisible();
    await expect(page.getByText("M : 0").locator("..")).toHaveClass(/border-red-500/);
    await expect(page.getByRole("radio", { name: "M" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "افزودن به سبد خرید" })).toBeDisabled();
    await page.getByRole("link", { name: "بازگشت به محصولات" }).click();
    await expect(page).toHaveURL(/\/fa\/products$/);
  });

  test("هر کارت رنگی صفحه مستقل دارد و فقط سایزهای همان رنگ را نمایش می‌دهد", async ({ page }) => {
    await page.goto("/fa/products/e2e-hoodie-01/black");
    await expect(page.getByRole("heading", { level: 1, name: "Hoodie 01" })).toBeVisible();
    let gallery = page.getByRole("region", { name: "تصاویر محصول" });
    await expect(gallery.getByRole("img")).toHaveAttribute("alt", "Hoodie 01 Black front");
    await expect(page.locator("section.min-w-0 > div.mt-2").getByText("Black", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "انتخاب رنگ White" })).toHaveCount(0);
    await expect(page.getByRole("radio", { name: "M" })).toBeEnabled();

    await page.goto("/fa/products/e2e-hoodie-01/white");
    gallery = page.getByRole("region", { name: "تصاویر محصول" });
    await expect(gallery.getByRole("img")).toHaveAttribute("alt", "Hoodie 01 White front");
    await expect(page.locator("section.min-w-0 > div.mt-2").getByText("White", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "انتخاب رنگ Black" })).toHaveCount(0);
    await expect(page.getByRole("radio", { name: "M" })).toBeDisabled();
  });

  test("قیمت تخفیف‌خورده فقط در صورت وجود نشان داده می‌شود", async ({ page }) => {
    await page.goto("/fa/products/e2e-hoodie-02");
    await expect(page.locator("del")).toHaveCount(1);
    await page.goto("/fa/products/e2e-hoodie-04");
    await expect(page.locator("del")).toHaveCount(0);
  });

  test("اشتراک‌گذاری محصول لینک صفحه همان محصول را در پنجره کپی می‌کند", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto("/fa/products/e2e-hoodie-01?color=white");

    await page.getByRole("button", { name: "اشتراک‌گذاری" }).click();
    const dialog = page.getByRole("dialog", { name: "اشتراک‌گذاری محصول" });
    await expect(dialog).toBeVisible();

    const expectedUrl = new URL("/fa/products/e2e-hoodie-01?color=white", page.url()).toString();
    const telegram = new URL((await dialog.getByRole("link", { name: "تلگرام" }).getAttribute("href"))!);
    expect(telegram.searchParams.get("url")).toBe(expectedUrl);

    await dialog.getByRole("button", { name: "کپی لینک محصول" }).click();
    await expect(dialog.getByRole("status")).toHaveText("لینک محصول کپی شد.");
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(expectedUrl);

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
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
    await expect(page).toHaveURL(/\/fa\/categories\/knitwear$/);
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
    await expect(page).toHaveURL(/draft_category=t-shirts/);
    await expect(page).toHaveURL(/filter_preview=1/);
    await expect(page).toHaveURL(/filters_open=1/);
    await expect(dialog).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "۶۰ محصول" })).toBeVisible();
    await expect(dialog.getByRole("checkbox", { name: "تی شرت" })).toBeChecked();
    await expect(dialog.getByRole("group", { name: "رنگ" })).toBeVisible();
    await expect(dialog.getByRole("group", { name: "سایز" })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "اعمال فیلترها (۳۰)" })).toBeVisible();

    await dialog.getByRole("button", { name: /اعمال فیلترها/ }).click();
    await expect(page).toHaveURL(/category=t-shirts/);
    await expect(page).not.toHaveURL(/draft_category=/);
    await expect(page).not.toHaveURL(/filter_preview=1/);
    await expect(dialog).toBeHidden();
    await expect(page.locator('a[href^="/fa/products/e2e-tee-"]')).toHaveCount(24);
    await expect(page.locator('a[href^="/fa/products/e2e-hoodie-"]')).toHaveCount(0);
  });

  test("صفحه جزئیات محصول در موبایل سرریز افقی ندارد", async ({ page }) => {
    await page.goto("/fa/products/e2e-hoodie-01");
    await expect(page.getByRole("heading", { level: 1, name: "Hoodie 01" })).toBeVisible();
    expect(await noHorizontalOverflow(page)).toBe(true);
  });
});
