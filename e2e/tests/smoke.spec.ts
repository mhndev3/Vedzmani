import { expect, test } from "@playwright/test";

test("frontend loads and reports backend status", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Vedzmani" })).toBeVisible();
  await expect(page.getByTestId("backend-status")).toContainText("ok");
});

test("backend readiness endpoint is healthy", async ({ request }) => {
  const res = await request.get("/api/health/ready/");
  expect(res.status()).toBe(200);
});