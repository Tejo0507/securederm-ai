import { defineConfig } from "@playwright/test";

/**
 * End-to-end tests (web/e2e). Locally they reuse whatever is already running
 * on :3000 and :8001; in CI they start the API and a production build.
 *
 *   npx playwright test                    # bundled Chromium (npx playwright install chromium)
 *   PW_CHANNEL=chrome npx playwright test  # or an installed Google Chrome
 */
const WEB_URL = process.env.E2E_WEB_URL ?? "http://localhost:3000";
export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8001";
const CI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  workers: CI ? 2 : undefined,
  reporter: CI ? [["github"], ["html", { open: "never" }]] : "list",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: WEB_URL,
    channel: process.env.PW_CHANNEL || undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { browserName: "chromium", viewport: { width: 1280, height: 800 } } },
    {
      // The narrowest width the layout supports without horizontal scrolling.
      name: "phone",
      use: { browserName: "chromium", viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
    },
  ],
  webServer: [
    {
      command: `${process.env.PYTHON ?? "python"} -m web_backend.main`,
      cwd: "..",
      url: `${API_URL}/api/health`,
      reuseExistingServer: !CI,
      timeout: 180_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      // CI builds first (see .github/workflows/ci.yml); locally this only
      // runs if nothing is listening on :3000 yet.
      command: CI ? "npm run start -- -p 3000" : "npm run dev -- -p 3000",
      url: WEB_URL,
      reuseExistingServer: !CI,
      timeout: 180_000,
    },
  ],
});
