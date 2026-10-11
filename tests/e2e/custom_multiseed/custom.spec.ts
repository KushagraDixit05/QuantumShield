import { test, expect, SSE_ABORT, settle } from "../shared/fixtures";
import { backendRun, openRun, runAndWait, setSeeds, readAccuracyTable, readRejectionLog } from "../shared/runner";
import { scenarioRows, storedRejections, TOL_EXACT } from "../shared/data";
import { assertUiEqualsBackend, chooseCustomLocal as chooseCustom, near, openTableViews, r4, readSeedTable } from "./util";

const CUSTOM = [
  { attack: "forged", defence: "on", aggregator: "fedavg" },
  { attack: "scaled", defence: "on", aggregator: "norm_filter" },
  { attack: "replay", defence: "on", aggregator: "median" },
] as const;

for (const c of CUSTOM) {
  test(`custom ${c.attack}/${c.defence}/${c.aggregator}, 5 rounds, seed 0: UI equals the backend run`, async ({ page, request, problems }) => {
    await openRun(page);
    await chooseCustom(page, c);
    await setSeeds(page, [0]);
    await runAndWait(page, 5);
    await expect(page.getByText(new RegExp(`attack\\s*${c.attack}.*aggregator\\s*${c.aggregator}`, "s")).first()).toBeVisible();
    const be = await backendRun(request, { attack: c.attack, defence: c.defence, aggregator: c.aggregator, seeds: [0], rounds: 5 });
    await assertUiEqualsBackend(page, be.events, [0], 5);
    expect(problems.filter((p) => !SSE_ABORT.test(p))).toEqual([]);
  });
}

for (const a of ["forged", "replay"] as const) {
  test(`custom ${a}/on/fedavg, 10 rounds, seed 0: UI equals scenarios.csv and rejections.csv`, async ({ page, request, problems }) => {
    await openRun(page);
    await chooseCustom(page, { attack: a, defence: "on", aggregator: "fedavg" });
    await setSeeds(page, [0]);
    await runAndWait(page, 10);
    await openTableViews(page);

    const row = scenarioRows().find((r) => r.attack === a && r.defence === "on" && r.seed === 0)!;
    expect(row, "stored scenarios.csv row exists").toBeTruthy();
    const seedTab = await readSeedTable(page);
    expect(seedTab).toHaveLength(1);
    near(seedTab[0].final, row.diverged_round === null ? row.final_acc : null, TOL_EXACT, "final accuracy vs scenarios.csv");
    expect(seedTab[0].divergedRound).toBe(row.diverged_round);

    const stored = storedRejections().filter((r) => r.attack === a && r.defence === "on" && r.seed === 0);
    expect(stored.length, "stored rejection rows").toBe(row.rejected);
    const ui = await readRejectionLog(page);
    expect(ui.map((r) => `${r.seed}|${r.round}|${r.client}|${r.raw}`).sort()).toEqual(stored.map((r) => `${r.seed}|${r.round}|${r.client}|${r.reason}`).sort());

    // also against the backend, per round
    const be = await backendRun(request, { attack: a, defence: "on", aggregator: "fedavg", seeds: [0], rounds: 10 });
    await assertUiEqualsBackend(page, be.events, [0], 10);
    const acc = await readAccuracyTable(page);
    near(acc[0][9], r4(be.events.filter((e) => e.type === "round" && e.seed === 0).slice(-1)[0].accuracy), TOL_EXACT, "last round");
    expect(problems.filter((p) => !SSE_ABORT.test(p))).toEqual([]);
    void settle;
  });
}
