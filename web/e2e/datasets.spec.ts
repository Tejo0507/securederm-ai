import { registerHospital, pngFile } from "./account";
import { expect, expectNoHorizontalOverflow, test } from "./fixtures";

/**
 * Uploading images, reading the storage summary and erasing images one at a
 * time, through the real UI against the real API. One signup covers the whole
 * story because signups are rate limited (10 per 5 minutes per address).
 * Needs the API's dev mode (see account.ts).
 */
test("a hospital can upload images, see its storage and delete them one by one", async ({ page, allowConsole }, testInfo) => {
  const account = await registerHospital(page, `datasets-${testInfo.project.name}`);
  try {
    await page.getByRole("tab", { name: "Datasets" }).click();
    const storage = page.getByRole("region", { name: "Storage" });
    const stored = page.getByRole("region", { name: "Stored images" });
    const files = page.locator("#dataset-files");

    // Nothing yet.
    await expect(storage.getByText("Nothing stored yet")).toBeVisible();
    await expect(stored.getByText("No images stored")).toBeVisible();

    // Three different images.
    await files.setInputFiles([pngFile("a.png", 200, 30, 30), pngFile("b.png", 30, 200, 30), pngFile("c.png", 30, 30, 200)]);
    await page.getByRole("button", { name: "Upload 3 images" }).click();
    await expect(page.getByText("Added 3 images (3 in total)")).toBeVisible();
    await expect(stored.getByRole("listitem")).toHaveCount(3);
    await expect(storage.getByText("PNG · 3")).toBeVisible();

    // One repeat and one new image: the repeat is not counted as added.
    await files.setInputFiles([pngFile("again.png", 200, 30, 30), pngFile("d.png", 120, 120, 30)]);
    await page.getByRole("button", { name: "Upload 2 images" }).click();
    await expect(page.getByText("Added 1 image, 1 already stored (4 in total)")).toBeVisible();
    await expect(stored.getByRole("listitem")).toHaveCount(4);

    // Only repeats.
    await files.setInputFiles([pngFile("a-again.png", 200, 30, 30)]);
    await page.getByRole("button", { name: "Upload", exact: true }).click();
    await expect(page.getByText(/Nothing new: that image was already stored \(4 images in total\)/)).toBeVisible();

    // Cancelling the confirmation keeps the image.
    const deleteFirst = stored.getByRole("button", { name: /^Delete image / }).first();
    await deleteFirst.click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();
    await expect(stored.getByRole("listitem")).toHaveCount(4);

    // Confirming erases exactly one, and the other panels follow.
    await deleteFirst.click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Delete image", exact: true }).click();
    await expect(stored.getByRole("listitem")).toHaveCount(3);
    await expect(page.getByText("1 dataset, 3 images in total.")).toBeVisible();
    await expect(storage.getByText("PNG · 3")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    // Erasing the rest one by one removes the dataset record with the last image.
    for (const remaining of [2, 1, 0]) {
      await deleteFirst.click();
      await page.getByRole("alertdialog").getByRole("button", { name: "Delete image", exact: true }).click();
      await expect(stored.getByRole("listitem")).toHaveCount(remaining);
    }
    await expect(stored.getByText("No images stored")).toBeVisible();
    await expect(page.getByText("No datasets yet")).toBeVisible();
  } finally {
    allowConsole(/401 \(Unauthorized\)/);
    await account.remove();
  }
});
