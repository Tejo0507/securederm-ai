import { expect, test } from "./fixtures";
import { mockApi } from "./mockApi";

const IDLE = { active: false, round: 0, total_rounds: 5, loss: 0, logs: [], metrics: [] };

/** The training tab polls; when a poll finds the session gone, say why. */
test("an expired session found while polling explains itself at sign-in", async ({ page, allowConsole }) => {
  allowConsole(/401 \(Unauthorized\)/);
  let polls = 0;
  await mockApi(page, {
    "GET /api/training/status": () =>
      ++polls > 1 ? { status: 401, body: { detail: "Invalid or expired token" } } : { body: IDLE },
    "POST /api/auth/logout": () => ({ body: { status: "logged_out" } }),
  });
  await page.clock.install();

  await page.goto("/dashboard#training");
  await expect(page.getByText("This is a simulated run")).toBeVisible();
  await page.clock.runFor(10_000);

  await page.waitForURL("**/login?reason=expired");
  await expect(page.getByText("Your session has ended.")).toBeVisible();
});
