import { expect, test } from "./fixtures";
import { mockApi } from "./mockApi";

/**
 * A download is a request like any other: if it is the one that discovers the
 * session has ended, the dashboard must send the user to sign in again rather
 * than showing "Not authenticated" beside the button.
 */
test("a download after the session ended leads to the sign-in page", async ({ page, allowConsole }) => {
  allowConsole(/401 \(Unauthorized\)/);
  await mockApi(page, {
    "GET /api/auth/export": () => ({ status: 401, body: { detail: "Not authenticated" } }),
  });

  await page.goto("/dashboard#settings");
  await page.getByRole("button", { name: "Download JSON" }).click();

  await page.waitForURL("**/login?reason=expired");
  await expect(page.getByText("Your session has ended.")).toBeVisible();
});
