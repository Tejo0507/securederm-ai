import { deflateSync } from "node:zlib";
import { expect, type Page } from "./fixtures";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8001";

/**
 * Registers a throwaway hospital through the real signup form and lands on its
 * dashboard (the API's dev mode hands the verification token straight back).
 * Call `remove()` in a `finally` so a run leaves no account behind.
 */
export async function registerHospital(page: Page, label: string, name = "E2E Test Hospital") {
  const email = `e2e-${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
  const password = `Tundra-${Math.random().toString(36).slice(2, 10)}-Velvet!`;

  await page.goto("/signup");
  await page.getByLabel("Hospital name").fill(name);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Location").fill("Testville");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create hospital account" }).click();
  await page.waitForURL("**/dashboard**");

  return {
    email,
    password,
    /** Deletes the account with the browser's own session, as the Settings danger zone does. */
    async remove() {
      const status = await page.evaluate(
        async ({ api, password }) => {
          const csrf = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1] ?? "";
          const res = await fetch(`${api}/api/auth/account`, {
            method: "DELETE",
            credentials: "include",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(csrf) },
            body: JSON.stringify({ password }),
          });
          return res.status;
        },
        { api: API_URL, password },
      );
      await page.goto("about:blank");
      expect(status, "test account cleanup").toBe(200);
    },
  };
}

function crc32(bytes: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1;
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type: string, data: Buffer): Buffer {
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, checksum]);
}

/**
 * A real, decodable PNG of one colour. Different colours give different pixels,
 * so the server stores them as different images (it names files by pixel hash).
 */
export function solidPng(r: number, g: number, b: number, size = 8): Buffer {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header.set([8, 2, 0, 0, 0], 8); // 8-bit, RGB, default compression, filter and interlace
  const row = Buffer.concat([Buffer.from([0]), Buffer.from(Array.from({ length: size }, () => [r, g, b]).flat())]);
  const raw = Buffer.concat(Array.from({ length: size }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngChunk("IHDR", header),
    pngChunk("IDAT", deflateSync(raw)),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
}

/** An image upload entry for `setInputFiles`. */
export const pngFile = (name: string, r: number, g: number, b: number) => ({
  name,
  mimeType: "image/png",
  buffer: solidPng(r, g, b),
});
