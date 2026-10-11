import { test } from "../shared/fixtures";
import { readRejectionLog } from "../shared/runner";
import { accuracyCells, checkCounts, expect, expectNumberNear, noProblems, perSeedRow, runPreset, source, TOL_DISPLAY_VS_6DP, TOL_EXACT } from "./common";

test("preset A (none/off), seed 0, 10 rounds matches demo/results", async ({ page, problems }) => {
  const { curve, row, rej } = source("A");
  await runPreset(page, "A");

  // A: per-round accuracy vs scenarios.json all["none/off"][r+1]
  const cells = await accuracyCells(page);
  expect(cells.length).toBe(10);
  cells.forEach((t, r) => expectNumberNear(t, curve[r + 1], TOL_DISPLAY_VS_6DP, `A round ${r}`));

  // A: final accuracy vs scenarios.csv final_acc
  const seed = await perSeedRow(page);
  expectNumberNear(seed.final, row.final_acc, TOL_EXACT, "A final accuracy");

  // A: no divergence (diverged_round blank), no rejections
  expect(row.diverged_round).toBeNull();
  expect(seed.divergence).toBe("none");
  expect(await page.locator(".qs-diverged").count()).toBe(0);
  expect(row.rejected).toBe(0);
  expect(rej.length).toBe(0);
  const log = page.locator("table", { has: page.locator("th", { hasText: /raw reason/i }) });
  if (await log.count()) expect(await readRejectionLog(page)).toEqual([]);
  await expect(page.getByText("No rejections received yet")).toBeVisible();

  // counts per round
  await checkCounts(page, "A");
  noProblems(problems);
});
