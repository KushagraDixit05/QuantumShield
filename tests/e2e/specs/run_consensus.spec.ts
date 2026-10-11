import { test, expect, settle, SHOTS } from "./fixtures";
import path from "node:path";

test("run scenario C (1 seed, 3 rounds) then verify its consensus certificate", async ({ page, problems }) => {
  await page.goto("/run");
  await settle(page);
  await expect(page.getByText(/ZK: replay only/).first()).toBeVisible();
  await page.getByRole("radio", { name: /^C[: ]/ }).check();
  // exactly one seed: 0
  for (const n of [1, 2, 3, 4]) {
    const box = page.getByRole("checkbox", { name: String(n), exact: true });
    if (await box.isChecked()) await box.uncheck();
  }
  const seed0 = page.getByRole("checkbox", { name: "0", exact: true });
  if (!(await seed0.isChecked())) await seed0.check();
  await page.getByLabel(/Rounds/).fill("3");
  await page.getByRole("button", { name: "Run", exact: true }).click();

  // streamed output
  await expect(page.getByText("Live output")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(".qs-bigbadge.live").first()).toBeVisible();
  await expect(page.getByText("Run failed or the stream was lost")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run", exact: true })).toBeEnabled({ timeout: 110_000 });
  const body = await page.locator("main").innerText();
  expect(body).toMatch(/accuracy/i);
  expect(body).toMatch(/accepted/i);
  expect(body).toMatch(/rejected/i);
  expect(await page.locator("svg .recharts-line-curve").count()).toBeGreaterThanOrEqual(1);
  // rejection log: norm gate label
  await expect(page.locator("td:visible", { hasText: "plaintext norm gate (not ZK)" }).first()).toBeVisible();
  await expect(page.locator("td:visible", { hasText: /norm_bound_exceeded/ }).first()).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "run.png"), fullPage: true });
  // run id shown
  const runId = (await page.locator("code.mono").first().innerText()).trim();
  expect(runId.length).toBeGreaterThan(4);

  // consensus
  await page.getByRole("link", { name: "Consensus" }).first().click();
  await expect(page).toHaveURL(/\/consensus/);
  // the run id is prefilled from sessionStorage but not auto-loaded: click Load
  await expect(page.getByRole("textbox", { name: "Run id" })).toHaveValue(runId);
  await page.getByRole("button", { name: "Load", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Rounds" })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("table tbody tr").first()).toBeVisible();
  await expect(page.getByText(/finalized/).first()).toBeVisible();
  const btn = page.getByRole("button", { name: "Verify certificate (public keys only)" }).first();
  await btn.click();
  await expect(page.getByText("✓ valid", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("quorum met")).toBeVisible();
  await expect(page.getByText(/Checked with public keys only/)).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "consensus.png"), fullPage: true });
  // Known benign: the SSE connection is aborted by client-side navigation away from /run (see ui-Q report, finding Q-3).
  expect(problems.filter((x) => !/requestfailed: GET .*\/stream net::ERR_ABORTED/.test(x))).toEqual([]);
});
