import { expect, test } from "./fixtures";
import { mockApi } from "./mockApi";

const NO_STATS = {
  hospitals: 60, models: 0, images: 0, rounds_recorded: 0,
  latest_round: null, latest_avg_loss: null, best_avg_loss: null,
};

const hospital = (id: number, name: string) => ({ id, name, location: "Testville" });

/**
 * "Show more" is still in flight when a new search finishes. The late page
 * belongs to the old list and must not replace the new results with it.
 */
test("a late directory page does not overwrite a newer search", async ({ page }) => {
  const everyone = Array.from({ length: 50 }, (_, i) => hospital(i + 1, `General ${i + 1}`));
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  let served = false;

  await mockApi(page, {
    "GET /api/federated/rounds": () => ({ body: [] }),
    "GET /api/network/stats": () => ({ body: NO_STATS }),
    "GET /api/hospitals": async (url) => {
      if (url.searchParams.get("q")) return { body: [hospital(99, "Searched Clinic")] };
      if (!url.searchParams.get("offset")) return { body: everyone };
      await held;
      served = true;
      return { body: [hospital(51, "Late Arrival")] };
    },
  });

  await page.goto("/dashboard#network");
  await page.getByRole("button", { name: "Show more" }).click();
  await page.getByRole("searchbox", { name: /Search hospitals/ }).fill("searched");
  await expect(page.getByText("Searched Clinic")).toBeVisible();

  release();
  await expect.poll(() => served).toBe(true);
  await page.waitForTimeout(500);   // give the late reply time to be applied

  await expect(page.getByText("Searched Clinic")).toBeVisible();
  await expect(page.getByText("Late Arrival")).toHaveCount(0);
  await expect(page.getByText("General 1", { exact: true })).toHaveCount(0);
  await expect(page.getByText("1 match")).toBeVisible();
});
