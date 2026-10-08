import { expect, test } from "@playwright/test";

test("root redirects to the default Persian locale (RTL)", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/fa$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("backend readiness endpoint is healthy", async ({ request }) => {
  const res = await request.get("/api/health/ready/");
  expect(res.status()).toBe(200);
});
