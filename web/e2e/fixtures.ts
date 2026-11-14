import { expect, test as base, type Page } from "@playwright/test";

/**
 * `test` with a console guard: any console error or uncaught page error
 * fails the test, unless the test allowed it with `allowConsole(/pattern/)`.
 * This is what caught the 401-on-every-page noise (#47) by hand.
 */
export const test = base.extend<{ allowConsole: (pattern: RegExp) => void }>({
  allowConsole: [
    async ({ page }, use) => {
      const allowed: RegExp[] = [];
      const problems: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() !== "error") return;
        const text = msg.text();
        if (!allowed.some((re) => re.test(text))) problems.push(`console.error: ${text}`);
      });
      page.on("pageerror", (err) => {
        if (!allowed.some((re) => re.test(err.message))) problems.push(`page error: ${err.message}`);
      });
      await use((pattern) => allowed.push(pattern));
      expect(problems, "unexpected console errors").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
export type { Page };

/** Fails if the page scrolls sideways, naming the widest offenders. */
export async function expectNoHorizontalOverflow(page: Page) {
  const report = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const over = document.documentElement.scrollWidth - width;
    if (over <= 0) return null;
    const culprits = [...document.querySelectorAll("body *")]
      .filter((el) => el.getBoundingClientRect().right > width + 1)
      .slice(0, 3)
      .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)}`);
    return `${over}px wider than the viewport: ${culprits.join(", ")}`;
  });
  expect(report, "horizontal overflow").toBeNull();
}
