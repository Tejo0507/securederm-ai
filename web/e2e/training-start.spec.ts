import { expect, test } from "./fixtures";
import { mockApi } from "./mockApi";

/**
 * Starting a second run: the log of the finished run is still on screen, which
 * used to end the "Starting..." state at once and re-enable the button while
 * the request was still in flight.
 */
test("the button stays in Starting until the new run is reported", async ({ page }) => {
  const finished = {
    active: false, round: 5, total_rounds: 5, loss: 0.9,
    logs: ["✓ Federated training complete!"], metrics: [{ round: 5, avg_loss: 0.9, nodes: 2 }],
  };
  const running = { ...finished, active: true, round: 1, logs: ["[Round 1] training locally..."], metrics: [] };
  let started = false;
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));

  await mockApi(page, {
    "GET /api/training/status": () => ({ body: started ? running : finished }),
    "POST /api/training/start": async () => {
      await held;
      started = true;
      return { body: { status: "started", total_rounds: 5 } };
    },
  });

  await page.goto("/dashboard#training");
  await expect(page.getByText("Federated training complete!")).toBeVisible();
  await page.getByRole("button", { name: "Start training" }).click();

  const starting = page.getByRole("button", { name: "Starting..." });
  await expect(starting).toBeDisabled();
  await page.waitForTimeout(1_000);   // the old code gave up long before this
  await expect(starting).toBeDisabled();

  release();
  await expect(page.getByRole("button", { name: "Round 1/5" })).toBeDisabled();
});
