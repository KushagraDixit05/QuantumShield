// Shared by the preset specs. Imports only from ../shared. Every expected value comes from demo/results at test time.
import type { Page } from "@playwright/test";
import { expect, settle, SSE_ABORT } from "../shared/fixtures";
import { choosePreset, runAndWait, setSeeds } from "../shared/runner";
import { PRESETS, TOL_DISPLAY_VS_6DP, TOL_EXACT, curves, scenarioRows, storedRejections } from "../shared/data";

export type Id = keyof typeof PRESETS;
export const ROUNDS = 10;
export const SEED = 0;

export async function runPreset(page: Page, id: Id) {
  await page.goto("/run");
  await settle(page);
  await choosePreset(page, id);
  await setSeeds(page, [SEED]);
  await runAndWait(page, ROUNDS);
  // the data tables sit inside collapsed <details><summary>Table view</summary>; innerText of a closed one is empty
  for (const s of await page.locator("details > summary", { hasText: "Table view" }).all()) {
    if (!(await s.evaluate((e) => (e.parentElement as HTMLDetailsElement).open))) await s.click();
  }
}

export function source(id: Id) {
  const { attack, defence } = PRESETS[id];
  const row = scenarioRows().find((r) => r.attack === attack && r.defence === defence && r.seed === SEED);
  if (!row) throw new Error(`scenarios.csv has no row ${attack}/${defence} seed ${SEED}`);
  const curve = curves().all[`${attack}/${defence}`];
  if (!curve || curve.length !== ROUNDS + 1) throw new Error(`scenarios.json ${attack}/${defence}: expected ${ROUNDS + 1} values`);
  const rej = storedRejections().filter((r) => r.attack === attack && r.defence === defence && r.seed === SEED);
  return { attack, defence, row, curve, rej };
}

/** Raw text of the seed-0 cell of each row of the per-round accuracy table (index = round). */
export async function accuracyCells(page: Page): Promise<string[]> {
  const table = page.locator("table", { has: page.locator("th", { hasText: /^round$/ }) }).first();
  const heads = (await table.locator("thead th").allInnerTexts()).map((h) => h.trim());
  const col = heads.map((h) => h.toLowerCase()).indexOf(`seed ${SEED}`);
  expect(col, `column "seed ${SEED}" in the per-round table (heads: ${heads.join("|")})`).toBeGreaterThanOrEqual(0);
  const out: string[] = [];
  for (const r of await table.locator("tbody tr").all()) {
    const cells = (await r.locator("td").allInnerTexts()).map((x) => x.trim());
    expect(Number(cells[0]), "round label").toBe(out.length);
    out.push(cells[col]);
  }
  return out;
}

export function expectNumberNear(text: string, expected: number, tol: number, what: string) {
  expect(text, `${what}: a number, got "${text}"`).toMatch(/^-?\d+\.\d{4}$/);
  expect(Math.abs(Number(text) - expected), `${what}: UI ${text} vs source ${expected}`).toBeLessThanOrEqual(tol);
}

/** Per-seed table row for SEED: [final cell text, divergence cell text]. */
export async function perSeedRow(page: Page) {
  const table = page.locator("table", { has: page.locator("caption", { hasText: "Per-seed result" }) });
  const rows = await table.locator("tbody tr").all();
  expect(rows.length, "one per-seed row").toBe(1);
  const c = (await rows[0].locator("td").allInnerTexts()).map((x) => x.trim());
  expect(Number(c[0])).toBe(SEED);
  return { final: c[1], divergence: c[2] };
}

/** Accepted/rejected counts table rows: [round, accepted, rejected, finalized]. */
export async function countsRows(page: Page) {
  const table = page.locator("table", { has: page.locator("th", { hasText: /^accepted$/ }) }).first();
  const out: { round: number; accepted: number | null; rejected: number | null }[] = [];
  for (const r of await table.locator("tbody tr").all()) {
    const c = (await r.locator("td").allInnerTexts()).map((x) => x.trim());
    const n = (t: string) => (/^\d+$/.test(t) ? Number(t) : null); // "n/a" -> null
    out.push({ round: Number(c[0]), accepted: n(c[1]), rejected: n(c[2]) });
  }
  return out;
}

/** `divergedRound`: the run stops there (no later round exists) and that round has no counts: both cells must read n/a. */
export async function checkCounts(page: Page, id: Id, divergedRound: number | null = null) {
  const { rej } = source(id);
  const clients = 5; // docs/e2e_map.md: clients = 5
  const rows = await countsRows(page);
  const expected = divergedRound === null ? ROUNDS : divergedRound + 1;
  expect.soft(rows.length, `counts table: rounds 0..${expected - 1}`).toBe(expected);
  for (const r of rows) {
    if (divergedRound !== null && r.round >= divergedRound) {
      expect(r.accepted, `round ${r.round} diverged: accepted must be n/a, not a number`).toBeNull();
      expect(r.rejected, `round ${r.round} diverged: rejected must be n/a, not a number`).toBeNull();
      continue;
    }
    const n = rej.filter((x) => x.round === r.round).length;
    expect(r.rejected, `round ${r.round} rejected`).toBe(n);
    expect(r.accepted, `round ${r.round} accepted`).toBe(clients - n);
  }
}

export function noProblems(problems: string[]) {
  expect(problems.filter((x) => !SSE_ABORT.test(x))).toEqual([]);
}

export { expect, TOL_DISPLAY_VS_6DP, TOL_EXACT };
