import { expect, test } from "./fixtures";
import { mockApi } from "./mockApi";

/** A failed "Resend verification email" must say why instead of doing nothing. */
test("a verification email that cannot be resent says why", async ({ page, allowConsole }) => {
  allowConsole(/403 \(Forbidden\)|429 \(Too Many Requests\)/);
  await mockApi(page, {
    "POST /api/auth/login": () => ({
      status: 403,
      body: { detail: "Email not verified. Check your inbox, or request a new link." },
    }),
    "POST /api/auth/resend-verification": () => ({
      status: 429,
      body: { detail: "Too many attempts. Please try again later." },
    }),
  });

  await page.goto("/login");
  await page.getByLabel("Work email").fill("pending@example.com");
  await page.getByLabel("Password", { exact: true }).fill("not-a-real-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  const resend = page.getByRole("button", { name: "Resend verification email" });
  await resend.click();

  await expect(page.getByText("Too many attempts. Please try again later.")).toBeVisible();
  await expect(resend).toBeEnabled();
});
