import { expect, test, type Page } from "./fixtures";

/** The theme as first painted: recorded at DOMContentLoaded, before React hydrates. */
async function recordFirstPaintTheme(page: Page) {
  await page.addInitScript(() => {
    document.addEventListener("DOMContentLoaded", () => {
      (window as unknown as { __firstTheme?: string }).__firstTheme = document.documentElement.dataset.theme;
    });
  });
}

const firstTheme = (page: Page) =>
  page.evaluate(() => (window as unknown as { __firstTheme?: string }).__firstTheme);

test.describe("theme switch (#54)", () => {
  test.describe("on a dark-mode OS", () => {
    test.use({ colorScheme: "dark" });

    test("follows the OS until a choice is made", async ({ page }) => {
      await recordFirstPaintTheme(page);
      await page.goto("/models");
      expect(await firstTheme(page)).toBe("dark");
    });

    test("a light choice wins over the OS from the first paint after reload", async ({ page, isMobile }) => {
      await recordFirstPaintTheme(page);
      await page.goto("/models");
      if (isMobile) await page.getByRole("button", { name: "Open menu" }).click();
      await page.getByRole("radio", { name: /Light/ }).first().click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

      await page.reload();
      expect(await firstTheme(page)).toBe("light");
    });
  });

  test("the choice carries across pages and back to system", async ({ page, isMobile }) => {
    await page.goto("/");
    const open = async () => {
      if (isMobile) await page.getByRole("button", { name: "Open menu" }).click();
    };
    await open();
    await page.getByRole("radio", { name: /Dark/ }).first().click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await page.evaluate(() => localStorage.getItem("theme"))).toBe("dark");

    await page.goto("/demo");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await open();
    await page.getByRole("radio", { name: /system/i }).first().click();
    await expect(page.locator("html")).toHaveAttribute("data-theme-pref", "system");
    expect(await page.evaluate(() => localStorage.getItem("theme"))).toBeNull();
  });

  test("arrow keys move the choice", async ({ page, isMobile }) => {
    test.skip(isMobile, "keyboard navigation is checked on desktop");
    await page.goto("/models");
    const light = page.getByRole("radio", { name: "Light" }).first();
    await light.click();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("radio", { name: "Dark" }).first()).toBeFocused();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });
});
