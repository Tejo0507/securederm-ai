import { registerHospital } from "./account";
import { expect, test } from "./fixtures";

// A zone far from UTC, so a timestamp read as local time instead of UTC is hours off.
test.use({ timezoneId: "Asia/Kolkata" });

/**
 * The Network tab and the Training tab, with one signup for both because
 * signups are rate limited (10 per 5 minutes per address).
 */
test("the directory can be searched and a training run shows up newest first", async ({ page, allowConsole }, testInfo) => {
  const tag = Date.now().toString(36);
  const name = `Searchable Clinic ${tag}`;
  const account = await registerHospital(page, `network-${testInfo.project.name}`, name);
  try {
    // The directory: a verified total, and a search that finds this hospital.
    await page.getByRole("tab", { name: "Network" }).click();
    await expect(page.getByText(/\d+ verified hospitals?/)).toBeVisible();

    const search = page.getByRole("searchbox", { name: /Search hospitals/ });
    await search.fill(name);
    await expect(page.getByText("1 match")).toBeVisible();
    await expect(page.getByRole("listitem").filter({ hasText: name })).toHaveCount(1);

    await search.fill(`nobody-called-this-${tag}`);
    await expect(page.getByText("No hospitals match")).toBeVisible();

    await search.fill("");
    await expect(page.getByText(/\d+ verified hospitals?/)).toBeVisible();

    // Training says it is simulated, and a started run can be stopped.
    await page.getByRole("tab", { name: "Training" }).click();
    await expect(page.getByText("This is a simulated run")).toBeVisible();

    await page.getByRole("button", { name: "Start training" }).click();
    // Round 1 is recorded about five seconds in (longer while the dev server is busy).
    await expect(page.getByText("[Round 1] Aggregator merging updates")).toBeVisible({ timeout: 30_000 });

    await page.getByRole("button", { name: "Stop", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Stop training" }).click();
    await expect(page.getByText("Idle", { exact: true })).toBeVisible();

    // The Network tab lists this run among the latest rounds (it used to show the
    // oldest round 5s instead). Other tests may be recording rounds at the same
    // time, so look at this hospital's own row.
    await page.getByRole("tab", { name: "Network" }).click();
    const first = page.locator("tbody tr", { hasText: name }).first();
    await expect(first).toContainText("R1");

    // Its time is when it happened, in this browser's zone (it used to be hours off).
    const completed = (await first.locator("td").last().innerText()).trim();
    const secondsAgo = await page.evaluate((text) => (Date.now() - new Date(text).getTime()) / 1000, completed);
    expect(secondsAgo).toBeGreaterThanOrEqual(-5);
    expect(secondsAgo).toBeLessThan(120);

    // Start and stop are in the account's activity, with the round reached.
    await page.getByRole("tab", { name: "Overview" }).click();
    const activity = page.locator("section", { hasText: "Recent account activity" });
    await expect(activity.getByText("Training started")).toBeVisible();
    // (The first letter is capitalised by CSS, so the text itself is lowercase.)
    await expect(activity.getByText(/training stopped\s*· at round \d/i)).toBeVisible();
  } finally {
    allowConsole(/401 \(Unauthorized\)/);
    await account.remove();
  }
});
