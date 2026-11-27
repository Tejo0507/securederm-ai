import { expect, test } from "./fixtures";
import { mockApi } from "./mockApi";

const series = (total: number) => [{ date: "2026-11-27", total, unknown: 0 }];

/** While a new range loads, the old range's total must not be captioned with it. */
test("the activity caption never mixes one range's total with another", async ({ page }) => {
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  await mockApi(page, {
    "GET /api/predictions/summary": () => ({
      body: {
        total: 3, unknown: 0, unknown_rate: 0, average_confidence: 0.9,
        first_at: null, last_at: null, by_class: { Burns: 3 }, by_model: [],
      },
    }),
    "GET /api/predictions": () => ({ body: { total: 0, items: [] } }),
    "GET /api/predictions/timeline": async (url) => {
      const days = Number(url.searchParams.get("days"));
      if (days === 30) return { body: { days, series: series(3) } };
      await held;
      return { body: { days, series: series(1) } };
    },
  });

  await page.goto("/dashboard#history");
  await expect(page.getByText("3 diagnoses in the last 30 days (UTC days)")).toBeVisible();

  await page.getByRole("button", { name: "7 days" }).click();
  await expect(page.getByText(/3 diagnoses in the last 7 days/)).toHaveCount(0);
  await expect(page.getByText("Loading...")).toBeVisible();

  release();
  await expect(page.getByText("1 diagnosis in the last 7 days (UTC days)")).toBeVisible();
});
