import { expect, expectNoHorizontalOverflow, test } from "./fixtures";

/**
 * When the account cannot be loaded and nothing is cached, the dashboard used
 * to show a spinner for ever. It must say so and offer another try.
 */
test("a dashboard that cannot load explains itself and can retry", async ({ page, allowConsole }) => {
  allowConsole(/503 \(Service Unavailable\)|401 \(Unauthorized\)/);
  let outage = true;
  await page.route("**/api/auth/me", async (route) => {
    if (!outage) return route.continue();
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      headers: {
        "Access-Control-Allow-Origin": new URL(page.url()).origin,
        "Access-Control-Allow-Credentials": "true",
      },
      body: JSON.stringify({ detail: "The service is restarting." }),
    });
  });

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Your dashboard could not be loaded" })).toBeVisible();
  await expect(page.getByText("The service is restarting.")).toBeVisible();
  await expectNoHorizontalOverflow(page);

  // Once the API answers again, retrying moves on (signed out here, so to sign-in).
  outage = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await page.waitForURL("**/login**");
});
