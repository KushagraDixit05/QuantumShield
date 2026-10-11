import { test, expect, SSE_ABORT, settle } from "../shared/fixtures";
import { choosePreset, openRun, runAndWait, setSeeds, readAccuracyTable } from "../shared/runner";
import { curves, mean, PRESETS, populationStd, scenarioRows, TOL_DISPLAY_VS_6DP, TOL_EXACT } from "../shared/data";
import { near, openTableViews, readSeedTable } from "./util";

type Id = keyof typeof PRESETS;

async function runPreset(page: import("@playwright/test").Page, id: Id, seeds: number[]) {
  await openRun(page);
  await choosePreset(page, id);
  await setSeeds(page, seeds);
  await runAndWait(page, 10);
  await openTableViews(page);
}

/** Checks shared by every multi-seed run. Returns the displayed per-seed table. */
async function checkSeeds(page: import("@playwright/test").Page, id: Id, seeds: number[]) {
  const { attack, defence } = PRESETS[id];
  const csv = scenarioRows().filter((r) => r.attack === attack && r.defence === defence);
  const tab = await readSeedTable(page);
  expect(tab.map((t) => t.seed).sort(), "one per-seed row per chosen seed").toEqual([...seeds].sort());
  for (const t of tab) {
    const row = csv.find((r) => r.seed === t.seed)!;
    expect(row, `scenarios.csv row for seed ${t.seed}`).toBeTruthy();
    near(t.final, row.diverged_round === null ? row.final_acc : null, TOL_EXACT, `seed ${t.seed} final vs scenarios.csv`);
    expect(t.divergedRound, `seed ${t.seed} diverged_round vs scenarios.csv`).toBe(row.diverged_round);
  }
  // one column per seed in the per-round table, one line per seed in the chart
  const acc = await readAccuracyTable(page);
  expect(Object.keys(acc).map(Number).sort()).toEqual([...seeds].sort());
  expect(await page.locator("svg .recharts-line-curve").count(), "one chart line per seed").toBe(seeds.length);
  for (const s of seeds) await expect(page.locator(".qs-legend", { hasText: `seed ${s}` }).first()).toBeVisible();
  // seed 0 per round vs scenarios.json (round r = index r + 1); stored 0.0 after divergence must show as DIVERGED (null)
  if (seeds.includes(0)) {
    const curve = curves().all[`${attack}/${defence}`];
    const d0 = csv.find((r) => r.seed === 0)!.diverged_round;
    // the stream stops at the divergence round: that round is the last row and shows DIVERGED
    expect(acc[0]).toHaveLength(d0 === null ? 10 : d0 + 1);
    acc[0].forEach((v, r) => {
      if (d0 !== null && r >= d0) expect(v, `seed 0 round ${r} must be DIVERGED, not a number`).toBeNull();
      else near(v, curve[r + 1], TOL_DISPLAY_VS_6DP, `seed 0 round ${r} vs scenarios.json`);
    });
  }
  // mean and std recomputed from the displayed finals (non-diverged seeds only) vs the CSV rows
  const shown = tab.filter((t) => t.final !== null).map((t) => t.final as number);
  const fromCsv = csv.filter((r) => seeds.includes(r.seed) && r.diverged_round === null).map((r) => r.final_acc);
  expect(shown.length, "number of non-diverged seeds").toBe(fromCsv.length);
  if (shown.length) near(mean(shown), mean(fromCsv), TOL_DISPLAY_VS_6DP, "mean over displayed finals vs CSV");
  if (shown.length > 1) near(populationStd(shown), populationStd(fromCsv), TOL_DISPLAY_VS_6DP, "std over displayed finals vs CSV");
  return { tab, shown };
}

for (const id of ["A", "C"] as const) {
  test(`multi-seed preset ${id}, seeds 0,1,2, 10 rounds: per-seed finals, columns, lines, mean/std`, async ({ page, problems }) => {
    await runPreset(page, id, [0, 1, 2]);
    await checkSeeds(page, id, [0, 1, 2]);
    expect(problems.filter((p) => !SSE_ABORT.test(p))).toEqual([]);
  });
}

test("multi-seed preset B, seeds 0,1,2: diverged_round per seed matches CSV and the mean excludes diverged seeds", async ({ page, problems }) => {
  await runPreset(page, "B", [0, 1, 2]);
  const { tab, shown } = await checkSeeds(page, "B", [0, 1, 2]);
  const csv = scenarioRows().filter((r) => r.attack === "scaled" && r.defence === "off");
  for (const t of tab) {
    expect(t.divergedRound).not.toBeNull();
    expect(t.final, "diverged seed must not show a number").toBeNull();
  }
  // every chosen seed diverges in the stored data, so no accuracy may enter a mean
  expect(shown).toEqual(csv.filter((r) => [0, 1, 2].includes(r.seed) && r.diverged_round === null).map((r) => r.final_acc));
  await expect(page.getByText(/seed 0 diverged at round \d+/)).toBeVisible();
  expect(problems.filter((p) => !SSE_ABORT.test(p))).toEqual([]);
});

// Mean/std of all five stored seeds: run page (recomputed), Overview summary table, attack heatmap (backend attack_matrix).
test("5-seed preset A: mean/std recomputed from displayed finals vs CSV, Overview summary table", async ({ page, problems }) => {
  await runPreset(page, "A", [0, 1, 2, 3, 4]);
  const { shown } = await checkSeeds(page, "A", [0, 1, 2, 3, 4]);
  expect(shown).toHaveLength(5);
  const m = mean(shown), sd = populationStd(shown);

  await page.goto("/");
  await settle(page);
  const rows = page.locator("table", { has: page.locator("th", { hasText: "std (population, n)" }) }).locator("tbody tr");
  await expect(rows.first()).toBeVisible();
  const all = await Promise.all((await rows.all()).map(async (r) => (await r.locator("td").allInnerTexts()).map((t) => t.trim())));
  const match = all.filter((c) => c[0] === "none" && c[1] === "off");
  expect(match, "exactly one none/off row in the Overview summary table").toHaveLength(1);
  const cells = match[0];
  expect(Number(cells[2]), "seeds").toBe(5);
  near(Number(/^-?\d+\.\d+/.exec(cells[4])![0]), m, TOL_DISPLAY_VS_6DP, "Overview mean final acc");
  near(Number(cells[5]), sd, TOL_DISPLAY_VS_6DP, "Overview std (population)");

  expect(problems.filter((p) => !SSE_ABORT.test(p))).toEqual([]);
});

// Same recomputation against the heatmap cell (backend attack_matrix). The heatmap prints 1-decimal percentages, so the
// comparison resolution is 0.05 percentage points.
test("5-seed preset A: mean/std recomputed from displayed finals vs attack heatmap cell", async ({ page, problems }) => {
  await runPreset(page, "A", [0, 1, 2, 3, 4]);
  const { shown } = await checkSeeds(page, "A", [0, 1, 2, 3, 4]);
  const m = mean(shown), sd = populationStd(shown);
  await page.goto("/attacks");
  await settle(page);
  const cell = page.getByRole("button", { name: /^attack none, defence off:/ });
  await expect(cell).toHaveCount(1);
  const txt = await cell.innerText();
  const pm = /(\d+(?:\.\d+)?)%/.exec(txt);
  const ps = /±\s*(\d+(?:\.\d+)?)%/.exec(txt);
  expect(pm, `heatmap mean in "${txt}"`).toBeTruthy();
  expect(ps, `heatmap std in "${txt}"`).toBeTruthy();
  // the heatmap prints percentages with 1 decimal: half a unit of that last digit is the display resolution
  near(Number(pm![1]), m * 100, 0.05 + 1e-9, "heatmap mean (%)");
  near(Number(ps![1]), sd * 100, 0.05 + 1e-9, "heatmap std (%)");
  expect(problems.filter((p) => !SSE_ABORT.test(p))).toEqual([]);
});
