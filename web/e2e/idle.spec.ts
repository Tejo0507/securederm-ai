import { registerHospital } from "./account";
import { expect, test } from "./fixtures";

const MINUTE = 60_000;

/**
 * Two dashboard tabs reach the idle warning together. "Stay signed in" in one
 * must also clear the other: that tab used to count down regardless and end
 * the session for both. Uses the default 15 minute timeout with a fake clock.
 */
test("staying signed in from one tab keeps every tab signed in", async ({ page, context, allowConsole }, testInfo) => {
  await context.clock.install();
  const account = await registerHospital(page, `idle-${testInfo.project.name}`);
  try {
    const other = await context.newPage();
    await other.goto("/dashboard");
    await expect(other.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await context.clock.fastForward(14 * MINUTE + 5_000);
    await context.clock.runFor(2_000);
    const warning = (p: typeof page) => p.getByRole("alertdialog", { name: "Still there?" });
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
  } finally {
    allowConsole(/401 \(Unauthorized\)/);
    await account.remove();
  }
});
