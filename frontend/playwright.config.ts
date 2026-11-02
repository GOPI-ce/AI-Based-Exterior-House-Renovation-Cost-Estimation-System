import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against a running app (frontend + API).
 *   npm run dev            (and the API on :8000)
 *   npm run test:e2e
 * Set E2E_BASE_URL to test a deployment, and E2E_AI=1 to include the live AI upload test.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    viewport: { width: 1440, height: 900 },
    acceptDownloads: true,
    trace: "retain-on-failure",
  },
  // PW_CHANNEL=chrome uses an installed Chrome instead of downloading Playwright's Chromium.
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, channel: process.env.PW_CHANNEL } }],
});
