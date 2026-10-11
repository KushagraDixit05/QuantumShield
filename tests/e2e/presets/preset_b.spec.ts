import { test } from "../shared/fixtures";
import { accuracyCells, checkCounts, expect, expectNumberNear, noProblems, perSeedRow, runPreset, source, TOL_DISPLAY_VS_6DP } from "./common";

test("preset B (scaled/off), seed 0, 10 rounds diverges where the CSV says", async ({ page, problems }) => {
  const { curve, row } = source("B");
  const d = row.diverged_round;
  expect(d, "scenarios.csv diverged_round for scaled/off seed 0").not.toBeNull();
  await runPreset(page, "B");

  const cells = await accuracyCells(page);
  // The run stops at the divergence round (backend/runner.py mirrors demo/run_demo.py:run_scenario, which returns
  // there), so rounds after it do not exist and are not listed. The stored 0.0 after it is the D-012 convention.
  expect(cells.length, `per-round table: rounds 0..${d}, the last one DIVERGED, nothing after it`).toBe(d! + 1);
  for (let r = 0; r < cells.length; r++) {
    if (r < d!) expectNumberNear(cells[r], curve[r + 1], TOL_DISPLAY_VS_6DP, `B round ${r}`);
    else {
      expect(cells[r], `B round ${r} must show the DIVERGED marker`).toMatch(/DIVERGED/);
      expect(cells[r], `B round ${r} must not show a number`).not.toMatch(/\d\.\d/);
      expect(cells[r]).not.toContain("0.0000");
    }
  }

  // per-seed table: DIVERGED at the CSV round, no number
  const seed = await perSeedRow(page);
  expect(seed.final).toMatch(new RegExp(`DIVERGED at round ${d}$`));
  expect(seed.final).not.toContain("0.0000");
  expect(seed.divergence).toBe(`from round ${d}`);

  // D-012 note visible, and it names the CSV round
  const note = page.getByRole("note").filter({ hasText: "D-012" });
  await expect(note).toBeVisible();
  await expect(note).toContainText(/convention, not a measured accuracy/);
  await expect(note).toContainText(`seed 0 diverged at round ${d}`);

  // no "0.0000" anywhere in the accuracy table / per-seed table
  await expect(page.locator("table td", { hasText: "0.0000" })).toHaveCount(0);

  await checkCounts(page, "B", d);
  noProblems(problems);
});
