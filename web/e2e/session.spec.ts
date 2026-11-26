import { registerHospital } from "./account";
import { expect, test } from "./fixtures";

/**
 * A download is a request like any other: if it is the one that discovers the
 * session has ended, the dashboard must send the user to sign in again rather
 * than showing "Not authenticated" beside the button.
 */
test("a download after the session ended leads to the sign-in page", async ({ page, context, allowConsole }, testInfo) => {
  const account = await registerHospital(page, `download-${testInfo.project.name}`);
  const cookies = await context.cookies();
  try {
    await page.getByRole("tab", { name: "Settings" }).click();
    await page.waitForLoadState("networkidle");

    // The session disappears underneath the open page.
    allowConsole(/401 \(Unauthorized\)/);
    await context.clearCookies();
    await page.getByRole("button", { name: "Download JSON" }).click();

    await page.waitForURL("**/login?reason=expired");
    await expect(page.getByText("Your session has ended.")).toBeVisible();
  } finally {
    await context.addCookies(cookies);
    await page.goto("/dashboard");
    await account.remove();
  }
});
