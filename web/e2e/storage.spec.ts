import { expect, test } from "./fixtures";
import { FAKE_HOSPITAL, mockApi } from "./mockApi";

/**
 * A browser that blocks site data throws on every localStorage access. The
 * session is a cookie, so signing up and using the dashboard must still work:
 * it used to report "Verification failed" after the account was verified.
 *
 * The API is mocked here and in the other single-behaviour tests: real signups
 * are rate limited (10 per 5 minutes per address) for the whole suite.
 */
test("registration and the dashboard work with browser storage blocked", async ({ page }) => {
  await page.addInitScript(() => {
    for (const method of ["getItem", "setItem", "removeItem"] as const) {
      Storage.prototype[method] = () => {
        throw new DOMException("blocked", "SecurityError");
      };
    }
  });
  await mockApi(page, {
    "POST /api/auth/verify-email": () => ({ body: FAKE_HOSPITAL }),
    "GET /api/datasets/summary": () => ({
      body: {
        images: 0, total_bytes: 0, formats: {}, quota: 20000, quota_used: 0,
        oldest_upload: null, newest_upload: null,
      },
    }),
    "GET /api/network/stats": () => ({
      body: {
        hospitals: 1, models: 0, images: 0, rounds_recorded: 0,
        latest_round: null, latest_avg_loss: null, best_avg_loss: null,
      },
    }),
    "GET /api/auth/activity": () => ({ body: [] }),
  });
  const heading = page.getByRole("heading", { level: 1, name: FAKE_HOSPITAL.name });

  await page.goto("/verify-email?token=a-single-use-token");
  await expect(page.getByText("Email verified")).toBeVisible();
  await page.waitForURL("**/dashboard**");
  await expect(heading).toBeVisible();

  // A full reload has no cached copy to paint from; the server answers.
  await page.reload();
  await expect(heading).toBeVisible();
});
