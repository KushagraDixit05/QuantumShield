import { test } from "../shared/fixtures";
import { readRejectionLog } from "../shared/runner";
import { accuracyCells, checkCounts, expect, expectNumberNear, noProblems, perSeedRow, runPreset, source, TOL_DISPLAY_VS_6DP, TOL_EXACT } from "./common";

test("preset C (scaled/on), seed 0, 10 rounds: numeric regression against demo/results", async ({ page, problems }) => {
  const { curve, row, rej } = source("C");
  await runPreset(page, "C");

  const cells = await accuracyCells(page);
  expect(cells.length).toBe(10);
  cells.forEach((t, r) => expectNumberNear(t, curve[r + 1], TOL_DISPLAY_VS_6DP, `C round ${r}`));

  const seed = await perSeedRow(page);
  expect(row.diverged_round).toBeNull();
  expect(seed.divergence).toBe("none");
  expectNumberNear(seed.final, row.final_acc, TOL_EXACT, "C final accuracy");

  // rejection log rows equal rejections.csv rows as a set (round, client, reason)
  const log = (await readRejectionLog(page)).map((r) => `${r.seed}|${r.round}|${r.client}|${r.raw}`).sort();
  const want = rej.map((r) => `${r.seed}|${r.round}|${r.client}|${r.reason}`).sort();
  expect(rej.length).toBe(row.rejected);
  expect(log).toEqual(want);

  await checkCounts(page, "C");
  noProblems(problems);
});
