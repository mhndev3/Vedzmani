import { defineConfig } from "@playwright/test";

// Run against the Docker Compose stack (Nginx on :8080) by default.
export default defineConfig({
  testDir: "./tests",
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    // Optional: drive an installed browser ("chrome", "msedge") when the bundled Chromium cannot be
    // downloaded (e.g. the Playwright CDN is geo-blocked). Unset = Playwright's own Chromium.
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    trace: "retain-on-failure",
  },
});