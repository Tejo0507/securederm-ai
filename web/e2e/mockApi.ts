import type { Page, Route } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8001";

export interface Reply {
  status?: number;
  body: unknown;
}
type Handler = (url: URL) => Reply | Promise<Reply>;

export const FAKE_HOSPITAL = {
  id: 1,
  name: "Mocked Clinic",
  email: "mocked@example.com",
  location: "Testville",
};

/**
 * Answers the page's API calls from `handlers` (keyed "METHOD /path"), for
 * states the real server cannot be put into on demand: failures, slow replies,
 * replies in a chosen order. The signed-in account is provided by default; a
 * call without a handler answers 404, so a test notices what it forgot.
 */
export async function mockApi(page: Page, handlers: Record<string, Handler>) {
  const all: Record<string, Handler> = {
    "GET /api/auth/me": () => ({ body: FAKE_HOSPITAL }),
    ...handlers,
  };
  await page.route(`${API_URL}/**`, async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const handler = all[`${request.method()} ${url.pathname}`];
    const reply = handler ? await handler(url) : { status: 404, body: { detail: "Not mocked" } };
    await route.fulfill({
      status: reply.status ?? 200,
      contentType: "application/json",
      headers: {
        "Access-Control-Allow-Origin": new URL(page.url()).origin,
        "Access-Control-Allow-Credentials": "true",
      },
      body: JSON.stringify(reply.body),
    });
  });
}
