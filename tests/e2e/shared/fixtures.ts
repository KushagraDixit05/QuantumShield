import { test as base, expect, type Page } from "@playwright/test";
import path from "node:path";
import { API_PORT, ROOT } from "./config";

export const API = `http://127.0.0.1:${API_PORT}`;
export const SHOTS = path.join(ROOT, "docs", "screenshots");

// The only tolerated network noise: the browser aborting an EventSource it closed itself.
export const SSE_ABORT = /requestfailed: GET .*\/stream net::ERR_ABORTED/;

/** `problems`: console errors, page errors and failed/4xx/5xx requests seen on the page. */
export const test = base.extend<{ problems: string[] }>({
  problems: async ({ page }, use) => {
    const problems: string[] = [];
    page.on("console", (m) => { if (m.type() === "error") problems.push(`console.error: ${m.text()}`); });
    page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
    page.on("requestfailed", (r) => problems.push(`requestfailed: ${r.method()} ${r.url()} ${r.failure()?.errorText}`));
    page.on("response", (r) => { if (r.status() >= 400) problems.push(`HTTP ${r.status()}: ${r.url()}`); });
    await use(problems);
  },
});
export { expect };

export async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.getByText(/Loading/i)).toHaveCount(0, { timeout: 20_000 }).catch(() => undefined);
}
