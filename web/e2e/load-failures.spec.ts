import { expect, test } from "./fixtures";
import { mockApi, type Reply } from "./mockApi";

/**
 * A request that failed is not an empty result. These sections used to claim
 * there was no activity, no data and no history when the API did not answer.
 */
const down = (): Reply => ({ status: 503, body: { detail: "The service is restarting." } });

test.beforeEach(({ allowConsole }) => allowConsole(/503 \(Service Unavailable\)/));

test("overview says what could not be loaded", async ({ page }) => {
  await mockApi(page, {
    "GET /api/datasets/summary": down,
    "GET /api/network/stats": down,
    "GET /api/auth/activity": down,
  });

  await page.goto("/dashboard");

  await expect(page.getByText("Activity unavailable")).toBeVisible();
  await expect(page.getByText("No activity yet")).toHaveCount(0);
  const images = page.locator("dl > div", { hasText: "Local images" });
  await expect(images).toContainText("n/a");
});

test("datasets, history and network offer the truth instead of an empty state", async ({ page }) => {
  let outage = true;
  await mockApi(page, {
    "GET /api/datasets": () => (outage ? down() : { body: [] }),
    "GET /api/datasets/summary": down,
    "GET /api/datasets/images": down,
    "GET /api/predictions": down,
    "GET /api/predictions/summary": down,
    "GET /api/federated/rounds": down,
    "GET /api/network/stats": down,
    "GET /api/hospitals": down,
  });

  await page.goto("/dashboard#data");
  await expect(page.getByText("Datasets unavailable")).toBeVisible();
  await expect(page.getByText("No datasets yet")).toHaveCount(0);
  outage = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("No datasets yet")).toBeVisible();

  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByText("History unavailable")).toBeVisible();
  await expect(page.getByText("No diagnoses yet")).toHaveCount(0);

  await page.getByRole("tab", { name: "Network" }).click();
  await expect(page.getByText("Rounds unavailable")).toBeVisible();
  await expect(page.getByText("The directory could not be loaded.")).toBeVisible();
  await expect(page.getByText("No hospitals registered yet")).toHaveCount(0);
});
