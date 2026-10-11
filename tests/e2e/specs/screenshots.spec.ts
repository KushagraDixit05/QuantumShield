import { test, expect, SHOTS, settle } from "./fixtures";
import path from "node:path";

const names: Record<string, string> = { "/": "overview", "/zk": "zk", "/overheads": "overheads", "/attacks": "attacks", "/limitations": "limitations" };

async function setTheme(page: import("@playwright/test").Page, t: "light" | "dark") {
  await page.addInitScript((v) => { try { localStorage.setItem("qs-theme", v); } catch {} }, t);
}

for (const [url, name] of Object.entries(names)) {
  test(`screenshot light ${name}`, async ({ page }) => {
    await setTheme(page, "light");
    await page.goto(url); await settle(page); await page.waitForTimeout(800);
    expect(await page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe("light");
    await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
  });
}
for (const [url, name] of [["/", "overview"], ["/attacks", "attacks"]]) {
  test(`screenshot dark ${name}`, async ({ page }) => {
    await setTheme(page, "dark");
    await page.goto(url); await settle(page); await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(SHOTS, `${name}-dark.png`), fullPage: true });
  });
}
test("screenshot phone /run", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  await page.goto("/run"); await settle(page); await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOTS, "run-phone.png"), fullPage: true });
  await ctx.close();
});
