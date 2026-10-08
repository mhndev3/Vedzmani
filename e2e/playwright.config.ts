import { defineConfig } from "@playwright/test";

// Run against the Docker Compose stack (Nginx on :8080) by default.
export default defineConfig({
  testDir: "./tests",
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
  },
});