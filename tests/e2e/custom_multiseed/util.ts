// Local helpers for custom_multiseed (imports only from ../shared).
import { expect, type Page } from "@playwright/test";
import { readAccuracyTable, readRejectionLog } from "../shared/runner";
import { TOL_EXACT } from "../shared/data";

export const r4 = (v: number) => Number(v.toFixed(4)); // the UI prints toFixed(4)

export function near(actual: number | null, expected: number | null, tol: number, what: string) {
  if (expected === null || actual === null) {
    expect(actual, what).toBe(expected);
    return;
  }
  expect(Math.abs(actual - expected), `${what}: UI ${actual} vs expected ${expected}`).toBeLessThanOrEqual(tol);
}

/** The accuracy table and the counts table sit inside closed <details>; open them so their text is rendered. */
export async function openTableViews(page: Page) {
  for (const s of await page.locator("details.qs-details > summary", { hasText: "Table view" }).all()) {
    const d = s.locator("xpath=..");
    if (!(await d.evaluate((e) => (e as HTMLDetailsElement).open))) await s.click();
  }
}

/** Per-seed result table: seed, final (null if DIVERGED), divergence column text. */
export async function readSeedTable(page: Page) {
  const table = page.locator("table", { has: page.locator("caption", { hasText: "Per-seed result" }) });
  const out: { seed: number; final: number | null; divergence: string; divergedRound: number | null }[] = [];
  for (const r of await table.locator("tbody tr").all()) {
    const c = (await r.locator("td").allInnerTexts()).map((x) => x.trim());
    const m = /^from round (\d+)$/.exec(c[2]);
    out.push({ seed: Number(c[0]), final: /^-?\d+\.\d+$/.test(c[1]) ? Number(c[1]) : null, divergence: c[2], divergedRound: m ? Number(m[1]) : null });
  }
  return out;
}

export type BackendRound = { seed: number; round: number; accuracy: number | null; diverged: boolean; rejections: { round: number; client: number | null; raw_reason: string }[] };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const roundsOf = (events: any[]): BackendRound[] => events.filter((e) => e.type === "round");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const doneOf = (events: any[]): { seed: number; final_accuracy: number | null; diverged_round: number | null }[] => {
  const d = events.find((e) => e.type === "done");
  expect(d, "backend stream ended with a done event").toBeTruthy();
  return d.results;
};

const key = (s: number | null, r: number, c: number | null, w: string) => `${s}|${r}|${c}|${w}`;

/** Compare the UI per-round table, per-seed table, rejection log and chart lines with a list of backend events. */
export async function assertUiEqualsBackend(page: Page, events: unknown[], seeds: number[], rounds: number) {
  await openTableViews(page);
  const rs = roundsOf(events as never[]);
  const ui = await readAccuracyTable(page);
  expect(Object.keys(ui).map(Number).sort(), "one accuracy column per seed").toEqual([...seeds].sort());
  for (const s of seeds) {
    const exp = rs.filter((r) => r.seed === s).sort((a, b) => a.round - b.round);
    expect(ui[s].length, `seed ${s} rows`).toBe(rounds);
    expect(exp.length, `backend seed ${s} rounds`).toBe(rounds);
    exp.forEach((e, i) => near(ui[s][i], e.diverged || e.accuracy === null ? null : r4(e.accuracy), TOL_EXACT, `seed ${s} round ${e.round} accuracy`));
  }
  const done = doneOf(events as never[]);
  const seedTab = await readSeedTable(page);
  expect(seedTab.map((x) => x.seed).sort(), "one per-seed row per chosen seed").toEqual([...seeds].sort());
  for (const d of done) {
    const u = seedTab.find((x) => x.seed === d.seed)!;
    near(u.final, d.diverged_round !== null || d.final_accuracy === null ? null : r4(d.final_accuracy), TOL_EXACT, `seed ${d.seed} final`);
    expect(u.divergedRound, `seed ${d.seed} diverged round`).toBe(d.diverged_round);
  }
  // rejection log (this session's run) vs backend rejections, as a multiset
  const uiRej = (await readRejectionLog(page)).map((x) => key(x.seed, x.round, x.client, x.raw)).sort();
  const beRej = rs.flatMap((r) => r.rejections.map((x) => key(r.seed, x.round, x.client, x.raw_reason))).sort();
  expect(uiRej, "rejection rows (seed|round|client|raw reason)").toEqual(beRej);
  // chart: one line per seed
  expect(await page.locator("svg .recharts-line-curve").count(), "one chart line per seed").toBe(seeds.length);
  if (seeds.length > 1) for (const s of seeds) await expect(page.locator(".qs-legend", { hasText: `seed ${s}` }).first()).toBeVisible();
}

/** Local replacement for shared/runner.ts chooseCustom: its getByLabel(/^Attack$/) and /^Defence$/ match nothing because
 *  the <label> text includes the <option> texts ("Attack scaledforgedreplay"). Requested in docs/status/gaps-C.md. */
export async function chooseCustomLocal(page: Page, o: { attack: string; defence: "on" | "off"; aggregator: string }) {
  await page.getByRole("radio", { name: /Custom attack and defence/ }).check();
  const sel = (re: RegExp) => page.locator("label:has(select)", { hasText: re }).locator("select");
  await sel(/^Attack/).selectOption(o.attack);
  await sel(/^Defence/).selectOption(o.defence);
  await sel(/^Aggregator/).selectOption(o.aggregator);
}
