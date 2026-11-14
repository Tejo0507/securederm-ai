import { expect, expectNoHorizontalOverflow, test } from "./fixtures";

const ROUTES = [
  { path: "/", title: "SecureDerm AI: federated wound imaging for hospitals" },
  { path: "/models", title: "Models · SecureDerm AI" },
  { path: "/demo", title: "Live simulation · SecureDerm AI" },
  { path: "/login", title: "Sign in · SecureDerm AI" },
  { path: "/signup", title: "Register your hospital · SecureDerm AI" },
  { path: "/verify-email", title: "Verify email · SecureDerm AI" },
];

for (const route of ROUTES) {
  test(`${route.path} renders with its own title and fits the screen`, async ({ page }) => {
    const response = await page.goto(route.path);
    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle(route.title);
    await expect(page.locator("h1")).toHaveCount(1);
    await page.waitForLoadState("networkidle");
    await expectNoHorizontalOverflow(page);
  });
}

test("a signed-out visitor makes no session request (#47)", async ({ page }) => {
  const probes: string[] = [];
  page.on("request", (r) => r.url().includes("/api/auth/me") && probes.push(r.url()));
  for (const path of ["/", "/models", "/login"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
  }
  expect(probes).toEqual([]);
});

test("an unknown route gets the 404 page", async ({ page, allowConsole }) => {
  // The browser logs the 404 document response itself.
  allowConsole(/404 \(Not Found\)/);
  const response = await page.goto("/no-such-page");
  expect(response?.status()).toBe(404);
  await expect(page).toHaveTitle("Page not found · SecureDerm AI");
  await expect(page.locator('main a[href="/"]').first()).toBeVisible();
});

test("models list loads with an accuracy meter per model", async ({ page }) => {
  await page.goto("/models");
  const meters = page.getByRole("meter");
  await expect(meters.first()).toBeVisible();
  const values = await meters.evaluateAll((els) => els.map((el) => Number(el.getAttribute("aria-valuenow"))));
  expect(values.length).toBeGreaterThan(0);
  for (const v of values) expect(v).toBeGreaterThanOrEqual(0);
});
