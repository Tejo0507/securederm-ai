import { expect, expectNoHorizontalOverflow, test } from "./fixtures";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8001";

const SECTIONS = [
  ["data", "Datasets"],
  ["predict", "Diagnose"],
  ["history", "History"],
  ["training", "Training"],
  ["network", "Network"],
  ["settings", "Settings"],
  ["overview", "Overview"],
] as const;

/**
 * The whole signed-in journey through the real UI against the real API:
 * register, land on the dashboard, visit every section, and delete the
 * account again so runs leave nothing behind. Needs the API's dev mode,
 * which hands the verification token straight back to the signup form.
 */
test("a new hospital can register and use every dashboard section", async ({ page, allowConsole }, testInfo) => {
  const email = `e2e-${testInfo.project.name}-${Date.now()}@example.com`;
  const password = `Tundra-${Math.random().toString(36).slice(2, 10)}-Velvet!`;

  await page.goto("/signup");
  await page.getByLabel("Hospital name").fill("E2E Test Hospital");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Location").fill("Testville");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create hospital account" }).click();
  await page.waitForURL("**/dashboard**");

  try {
    await expect(page.getByRole("heading", { level: 1, name: "E2E Test Hospital" })).toBeVisible();

    // A brand-new account's history starts at its own signup, even if the
    // database handed it a deleted account's id (fixed in #56).
    const activity = page.locator("section", { hasText: "Recent account activity" });
    await expect(activity.getByText("Email verified")).toBeVisible();
    await expect(activity.getByText("Account deleted")).toHaveCount(0);

    for (const [key, label] of SECTIONS) {
      await page.getByRole("tab", { name: label }).click();
      await expect(page).toHaveURL(new RegExp(`#${key}$`));
      await expect(page).toHaveTitle(`${label} · Dashboard · SecureDerm AI`);
      await page.waitForLoadState("networkidle");
      await expectNoHorizontalOverflow(page);
    }

    // A deep link names its section in the title on first load (#65).
    await page.goto("/dashboard#history");
    await expect(page).toHaveTitle("History · Dashboard · SecureDerm AI");
  } finally {
    // Delete the account with the browser's own session (cookies + CSRF),
    // the same request the Settings danger zone sends. Requests the open
    // dashboard makes after that are expected to come back 401.
    allowConsole(/401 \(Unauthorized\)/);
    const status = await page.evaluate(
      async ({ api, password }) => {
        const csrf = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1] ?? "";
        const res = await fetch(`${api}/api/auth/account`, {
          method: "DELETE",
          credentials: "include",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(csrf) },
          body: JSON.stringify({ password }),
        });
        return res.status;
      },
      { api: API_URL, password },
    );
    await page.goto("about:blank");
    expect(status, "test account cleanup").toBe(200);
  }
});
