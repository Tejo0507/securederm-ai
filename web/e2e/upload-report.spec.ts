import { pngFile } from "./account";
import { expect, test } from "./fixtures";
import { mockApi } from "./mockApi";

const EMPTY_SUMMARY = {
  images: 0, total_bytes: 0, formats: {}, quota: 20000, quota_used: 0,
  oldest_upload: null, newest_upload: null,
};

/** Files that were not stored must be reported, not silently dropped. */
test("an upload says which files did not make it in", async ({ page }) => {
  let sent = 0;
  await mockApi(page, {
    "GET /api/datasets": () => ({ body: [] }),
    "GET /api/datasets/summary": () => ({ body: EMPTY_SUMMARY }),
    "GET /api/datasets/images": () => ({ body: { total: 0, items: [] } }),
    "POST /api/datasets/upload": () => {
      sent += 1;
      // Two files arrive; the server could read only one of them.
      return { body: { uploaded: 1, duplicates: 0, total_images: 1, quota_reached: false } };
    },
  });
  await page.goto("/dashboard#data");
  const files = page.locator("#dataset-files");

  await files.setInputFiles([
    pngFile("good.png", 200, 30, 30),
    { name: "broken.png", mimeType: "image/png", buffer: Buffer.from("not an image") },
    { name: "huge.png", mimeType: "image/png", buffer: Buffer.alloc(10 * 1024 * 1024 + 1) },
  ]);
  await page.getByRole("button", { name: "Upload 3 images" }).click();

  await expect(
    page.getByText(
      "Added 1 image (1 in total). 1 file was over 10 MB and not sent. 1 file was skipped: not a readable image.",
    ),
  ).toBeVisible();
  expect(sent).toBe(1);

  // Only oversized files: nothing is sent at all.
  await files.setInputFiles([
    { name: "huge.png", mimeType: "image/png", buffer: Buffer.alloc(10 * 1024 * 1024 + 1) },
  ]);
  await page.getByRole("button", { name: "Upload", exact: true }).click();
  await expect(page.getByText("No images were added. 1 file was over 10 MB and not sent.")).toBeVisible();
  expect(sent).toBe(1);
});
