import { expect, test } from "@playwright/test";

test("storefront uses Persian RTL and the header contains only the agreed links", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/fa/about");
  await expect(page.locator("html")).toHaveAttribute("lang", "fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  const nav = page.getByRole("navigation", { name: "ناوبری اصلی" });
  for (const name of ["همه محصولات", "درباره ما", "سوالات متداول", "پشتیبانی"]) {
    await expect(nav.getByRole("link", { name })).toBeVisible();
  }
  for (const removed of ["تماس با ما", "بازگشت کالا", "پروفایل", "سبد خرید"]) {
    await expect(nav.getByRole("link", { name: removed })).toHaveCount(0);
  }
  await expect(page.getByRole("link", { name: "حساب کاربری" })).toBeVisible();
});


test("mobile viewport fills the device width without horizontal page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/fa");

  const viewport = page.locator('meta[name="viewport"]');
  await expect(viewport).toHaveAttribute("content", /width=device-width/);
  await expect(viewport).toHaveAttribute("content", /initial-scale=1/);

  const dimensions = await page.evaluate(() => {
    const documentWidth = document.documentElement.clientWidth;
    const offenders = [...document.querySelectorAll<HTMLElement>("body *")]
      .filter((element) => {
        // Carousel cards may sit outside the visible viewport by design, but only
        // inside their own horizontal scroll container. They must not count as
        // document-level overflow.
        return !element.parentElement?.closest('[style*="overflow"], .overflow-x-auto, .overflow-x-scroll');
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          id: element.id,
          className: typeof element.className === "string" ? element.className.slice(0, 140) : "",
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        };
      })
      .filter((element) => element.width > documentWidth + 1 || element.left < -1 || element.right > documentWidth + 1)
      .sort((a, b) => b.width - a.width)
      .slice(0, 8);
    return {
      innerWidth: window.innerWidth,
      documentWidth,
      bodyWidth: document.body.getBoundingClientRect().width,
      scrollWidth: document.documentElement.scrollWidth,
      heroWidth: document.querySelector("section[aria-label='بنر ویژه ودزمانی']")?.getBoundingClientRect().width ?? 0,
      categoriesWidth: document.querySelector("section[aria-labelledby='home-categories']")?.getBoundingClientRect().width ?? 0,
      offenders,
    };
  });

  expect(dimensions.documentWidth).toBeGreaterThanOrEqual(389);
  expect(dimensions.bodyWidth).toBeGreaterThanOrEqual(389);
  expect(dimensions.scrollWidth, JSON.stringify(dimensions)).toBeLessThanOrEqual(dimensions.documentWidth + 1);
  expect(dimensions.heroWidth).toBeGreaterThan(350);
  expect(dimensions.categoriesWidth).toBeGreaterThan(350);
  expect(dimensions.offenders, JSON.stringify(dimensions.offenders)).toEqual([]);
});

test("homepage product carousel scrolls internally without widening the page", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/fa");
  const track = page.locator("section[aria-labelledby='home-newest-products'] [dir='rtl']");
  await expect(track).toBeVisible();
  const before = await track.evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
    pageWidth: document.documentElement.scrollWidth,
  }));
  expect(before.scrollWidth).toBeGreaterThan(before.clientWidth);
  await track.evaluate((element) => {
    element.scrollTo({ left: -element.scrollWidth, behavior: "instant" });
  });
  const after = await track.evaluate((element) => ({
    scrollLeft: element.scrollLeft,
    pageWidth: document.documentElement.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  expect(after.scrollLeft).toBeLessThan(0);
  expect(after.pageWidth).toBeLessThanOrEqual(after.clientWidth + 1);
});

test("hero banner uses supplied VZ artwork and is not a link", async ({ page }) => {
  await page.goto("/fa");
  const hero = page.locator("section[aria-label='بنر ویژه ودزمانی']");
  await expect(hero).toBeVisible();
  await expect(hero.locator("img")).toHaveAttribute("src", /vedzmani-banner-vz\.svg/);
  await expect(hero.locator("a")).toHaveCount(0);
});

test("homepage shows the requested square categories and newest seven products", async ({ page }) => {
  await page.goto("/fa");

  const categories = page.locator("section[aria-labelledby='home-categories']");
  await expect(categories.getByRole("link")).toHaveCount(5);
  await expect(categories.locator("ul")).toHaveClass(/sm:grid-cols-6/);
  await expect(categories.locator("li").nth(0)).toHaveClass(/sm:col-span-2/);
  await expect(categories.locator("li").nth(2)).toHaveClass(/sm:col-span-2/);
  await expect(categories.locator("li").nth(3)).toHaveClass(/sm:col-span-3/);
  await expect(categories.locator("li").nth(4)).toHaveClass(/sm:col-span-3/);
  const expectedCategories = [
    { name: "دورس", href: "/fa/categories/sweatshirts" },
    { name: "بافت", href: "/fa/categories/knitwear" },
    { name: "شلوار جین", href: "/fa/categories/jeans" },
    { name: "جکت چرم", href: "/fa/categories/leather-jackets" },
    { name: "هودی", href: "/fa/categories/hoodies" },
  ];
  for (const category of expectedCategories) {
    const link = categories.getByRole("link", { name: category.name, exact: true });
    await expect(link).toHaveAttribute("href", category.href);
    await expect(link).toHaveClass(/aspect-square/);
    await expect(link).toHaveClass(/rounded-2xl/);
  }
  const categoryImage = categories.locator("img").first();
  await expect(categoryImage).toHaveAttribute("src", /\/media\//);
  await expect(categoryImage).not.toHaveAttribute("src", /_next\/image/);

  const newest = page.locator("section[aria-labelledby='home-newest-products']");
  await expect(newest.getByRole("heading", { name: "جدیدترین‌ها" })).toBeVisible();
  await expect(newest.locator("[dir='rtl'] > ul > li")).toHaveCount(7);
});

test("joggers category uses the requested Persian label", async ({ page }) => {
  await page.goto("/fa/categories/joggers");
  await expect(page.getByRole("heading", { level: 1, name: "شلوار جاگر" })).toBeVisible();
});

test("theme toggle switches dark mode and persists", async ({ page }) => {
  await page.goto("/fa");
  const html = page.locator("html");
  await page.getByRole("button", { name: "حالت تیره" }).click();
  await expect(html).toHaveClass(/dark/);
  await page.reload();
  await expect(html).toHaveClass(/dark/);
});

test("hamburger menu contains the requested categories and support links", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/fa");
  await page.getByRole("button", { name: "باز کردن منو" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.locator("summary").filter({ hasText: "دسته‌بندی‌ها" }).click();
  const categories = [
    { name: "دورس" },
    { name: "پیراهن" },
    { name: "تی شرت" },
    { name: "هودی" },
    { name: "کاپشن" },
    { name: "جکت", href: "/fa/categories/jackets" },
    { name: "جکت چرم", href: "/fa/categories/leather-jackets" },
    { name: "شلوار جین" },
    { name: "شلوار پارچه ای" },
    { name: "شلوار جاگر" },
    { name: "کتونی" },
    { name: "اکسسوری" },
  ];
  for (const category of categories) {
    const link = dialog.getByRole("link", { name: category.name, exact: true });
    await expect(link).toBeVisible();
    if (category.href) await expect(link).toHaveAttribute("href", category.href);
  }
  for (const name of ["همه محصولات", "درباره ما", "سوالات متداول", "پشتیبانی"]) {
    await expect(dialog.getByRole("link", { name, exact: true })).toBeVisible();
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("cart icon badge stays current when the initial cart request resolves after add-to-cart", async ({ page }) => {
  let releaseInitialGet!: () => void;
  const initialGet = new Promise<void>((resolve) => {
    releaseInitialGet = resolve;
  });
  let initialGetPending = true;

  await page.route("**/api/cart/", async (route) => {
    if (initialGetPending) {
      initialGetPending = false;
      await initialGet;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ item_count: 0 }),
    });
  });
  await page.route("**/api/auth/csrf/", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ csrfToken: "e2e-csrf" }) }),
  );
  await page.route("**/api/cart/items/", (route) =>
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ item_count: 1 }),
    }),
  );

  await page.goto("/fa/products/e2e-hoodie-01");
  const cartUpdated = page.evaluate(
    () => new Promise<void>((resolve) => window.addEventListener("vedzmani:cart-updated", () => resolve(), { once: true })),
  );
  await page.locator("label").filter({ has: page.getByRole("radio", { name: "M" }) }).click();
  await page.getByRole("button", { name: "افزودن به سبد خرید" }).click();
  await cartUpdated;

  // Release the stale initial GET only after the successful mutation event reached the header.
  releaseInitialGet();
  await expect(page.getByRole("link", { name: "سبد خرید، ۱ کالا" })).toBeVisible();
});

test("header hides while scrolling and returns after scrolling stops", async ({ page }) => {
  await page.goto("/fa/products");
  const menuButton = page.getByRole("button", { name: "باز کردن منو" });
  await menuButton.click();
  await page.keyboard.press("Escape");
  const header = page.locator("header").first();
  await page.evaluate(() => window.dispatchEvent(new Event("scroll")));
  await expect(header).toHaveAttribute("aria-hidden", "true");
  await expect(header).toHaveAttribute("aria-hidden", "false", { timeout: 1500 });
});

test("header search opens and blank search does not show products", async ({ page }) => {
  await page.goto("/fa");
  await page.getByRole("button", { name: "جستجوی محصولات" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("list")).toHaveCount(0);
  await expect(dialog.getByText("جستجوهای اخیر")).toHaveCount(0);
});
