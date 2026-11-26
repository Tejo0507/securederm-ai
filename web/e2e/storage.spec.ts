import { registerHospital } from "./account";
import { expect, test } from "./fixtures";

/**
 * A browser that blocks site data throws on every localStorage access. The
 * session is a cookie, so signing up and using the dashboard must still work:
 * it used to report "Verification failed" after the account was verified.
 */
test("registration and the dashboard work with browser storage blocked", async ({ page, allowConsole }, testInfo) => {
  await page.addInitScript(() => {
    for (const method of ["getItem", "setItem", "removeItem"] as const) {
      Storage.prototype[method] = () => {
        throw new DOMException("blocked", "SecurityError");
      };
    }
  });

  const account = await registerHospital(page, `storage-${testInfo.project.name}`);
  try {
    await expect(page.getByRole("heading", { level: 1, name: "E2E Test Hospital" })).toBeVisible();

    // A full reload has no cached copy to paint from; the server answers.
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "E2E Test Hospital" })).toBeVisible();
  } finally {
    allowConsole(/401 \(Unauthorized\)/);
    await account.remove();
  }
});
