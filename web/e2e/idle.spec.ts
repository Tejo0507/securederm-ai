import { expect, test, type Page } from "./fixtures";
import { mockApi } from "./mockApi";

const MINUTE = 60_000;

/**
 * Two dashboard tabs reach the idle warning together. "Stay signed in" in one
 * must also clear the other: that tab used to count down regardless and end
 * the session for both. Uses the default 15 minute timeout with a fake clock.
 */
test("staying signed in from one tab keeps every tab signed in", async ({ page, context }) => {
  await context.clock.install();
  const other = await context.newPage();
  for (const tab of [page, other]) {
    await mockApi(tab, {
      "POST /api/auth/logout": () => ({ body: { status: "logged_out" } }),
    });
    await tab.goto("/dashboard#settings");
    await expect(tab.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
  }

  await context.clock.fastForward(14 * MINUTE + 5_000);
  await context.clock.runFor(2_000);
  const warning = (tab: Page) => tab.getByRole("alertdialog", { name: "Still there?" });
  await expect(warning(page)).toBeVisible();
  await expect(warning(other)).toBeVisible();

  await other.getByRole("button", { name: "Stay signed in" }).click();
  await context.clock.runFor(2_000);
  await expect(warning(other)).toBeHidden();
  await expect(warning(page)).toBeHidden();

  // Past the first tab's original deadline, both are still on the dashboard.
  await context.clock.fastForward(2 * MINUTE);
  await context.clock.runFor(2_000);
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(other).toHaveURL(/\/dashboard/);
  await other.close();
});
