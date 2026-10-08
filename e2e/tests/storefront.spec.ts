import { expect, test } from "@playwright/test";

test("language switcher keeps the route and flips direction", async ({ page }) => {
  await page.goto("/fa/about");
  await page.getByRole("link", { name: /English/ }).first().click();
  await expect(page).toHaveURL(/\/en\/about$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("theme toggle switches dark mode and persists", async ({ page }) => {
  await page.goto("/en");
  const html = page.locator("html");
  await page.getByRole("button", { name: "Dark mode" }).click();
  await expect(html).toHaveClass(/dark/);
  await page.reload();
  await expect(html).toHaveClass(/dark/);
});

test("desktop navigation exposes the storefront pages", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/en");
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  for (const name of ["About", "Contact", "Returns", "FAQ", "Support", "Profile"]) {
    await expect(nav.getByRole("link", { name })).toBeVisible();
  }
});

test("mobile menu opens, navigates and closes", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto("/en");
  await page.getByRole("button", { name: "Open menu" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await page.getByRole("button", { name: "Open menu" }).click();
  await dialog.getByRole("link", { name: "FAQ" }).click();
  await expect(page).toHaveURL(/\/en\/faq$/);
  await expect(dialog).toBeHidden();
});
