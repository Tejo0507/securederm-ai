import { expect, test } from "./fixtures";

/** Whether this browser can give the page a WebGL context (CI GPUs vary). */
async function hasWebGL(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") ?? c.getContext("webgl"));
  });
}

test.describe("3D hero", () => {
  test("renders the scene with round controls, or the 2D graph without WebGL", async ({ page }) => {
    await page.goto("/");
    const stage = page.locator("figure").first();
    if (await hasWebGL(page)) {
      // The scene is a lazily loaded chunk; a cold dev server compiles it on demand.
      await expect(stage.locator("canvas")).toBeVisible({ timeout: 30_000 });
      await expect(stage.getByText("Live simulation")).toBeVisible();
      for (const site of ["Hospital A", "Hospital E"]) await expect(stage.getByText(site)).toBeAttached();
    } else {
      await expect(page.locator("canvas")).toHaveCount(0);
      await expect(page.getByText("Aggregator").first()).toBeVisible();
    }
  });

  test("the round can be paused and stepped through", async ({ page }) => {
    await page.goto("/");
    test.skip(!(await hasWebGL(page)), "needs WebGL for the 3D stage");

    const pause = page.getByRole("button", { name: "Pause the round" });
    await expect(pause).toBeVisible();
    await pause.click();
    await expect(page.getByRole("button", { name: "Play the round" })).toBeVisible();

    const average = page.getByRole("button", { name: /Average/ });
    await average.click();
    await expect(average).toHaveAttribute("aria-current", "step");
    await expect(page.getByText("FedAvg merges every update into one model.")).toBeVisible();
  });

  test.describe("with reduced motion", () => {
    test.use({ reducedMotion: "reduce" });

    test("falls back to the static 2D graph", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByText("Aggregator").first()).toBeVisible();
      await expect(page.locator("canvas")).toHaveCount(0);
    });
  });

  test("headline stays on three lines", async ({ page }) => {
    await page.goto("/");
    const lines = await page.locator("h1 > span").evaluateAll((spans) =>
      spans.map((s) => {
        const lineHeight = parseFloat(getComputedStyle(s.parentElement!).lineHeight);
        return Math.round(s.getBoundingClientRect().height / lineHeight);
      }),
    );
    expect(lines).toEqual([1, 1, 1]);
  });
});
