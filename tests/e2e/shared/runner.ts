// Drive /run and read what it shows. Selectors mirror frontend/components/scenario/RunView.tsx.
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { API, settle } from "./fixtures";

export async function openRun(page: Page) {
  await page.goto("/run");
  await settle(page);
}

export async function choosePreset(page: Page, id: "A" | "B" | "C") {
  await page.getByRole("radio", { name: /Preset A \/ B \/ C/ }).check();
  await page.getByRole("radio", { name: new RegExp(`^${id}[: ]`) }).check();
}

export async function chooseCustom(page: Page, o: { attack: string; defence: "on" | "off"; aggregator: string }) {
  await page.getByRole("radio", { name: /Custom attack and defence/ }).check();
  await page.getByLabel(/^Attack$/).selectOption(o.attack);
  await page.getByLabel(/^Defence$/).selectOption(o.defence);
  await page.getByLabel(/^Aggregator/).selectOption(o.aggregator);
}

export async function setSeeds(page: Page, seeds: number[]) {
  for (const n of [0, 1, 2, 3, 4]) {
    const box = page.getByRole("checkbox", { name: String(n), exact: true });
    if ((await box.isChecked()) !== seeds.includes(n)) await box.setChecked(seeds.includes(n));
  }
}

export async function runAndWait(page: Page, rounds: number) {
  await page.getByLabel(/Rounds/).fill(String(rounds));
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.getByText("Live output")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: "Run", exact: true })).toBeEnabled({ timeout: 220_000 });
  await expect(page.getByText("Run failed or the stream was lost")).toHaveCount(0);
}

/** "seed 0" column values of the per-round accuracy table: one entry per round; null = DIVERGED marker. */
/** The chart tables sit in collapsed <details> ("Table view"); open them so their text is readable. */
export async function openTableViews(page: Page) {
  await page.locator("details").evaluateAll((els) => els.forEach((e) => ((e as HTMLDetailsElement).open = true)));
}

export async function readAccuracyTable(page: Page): Promise<Record<number, (number | null)[]>> {
  await openTableViews(page);
  const table = page.locator("table", { has: page.locator("th", { hasText: /^round$/i }) }).first();
  const heads = await table.locator("thead th").allInnerTexts();
  const rows = await table.locator("tbody tr").all();
  const out: Record<number, (number | null)[]> = {};
  heads.forEach((h, i) => { const m = /^seed (\d+)/i.exec(h.trim()); if (m) out[Number(m[1])] = []; void i; });
  for (const r of rows) {
    const cells = await r.locator("td").allInnerTexts();
    heads.forEach((h, i) => {
      const m = /^seed (\d+)/i.exec(h.trim());
      if (!m) return;
      const t = cells[i].trim();
      out[Number(m[1])].push(/^-?\d+\.\d+$/.test(t) ? Number(t) : null);
    });
  }
  return out;
}

/** Per-seed result table: final accuracy (null if diverged) and diverged round. */
export async function readPerSeedResults(page: Page): Promise<Record<number, { final: number | null; diverged: boolean }>> {
  await openTableViews(page);
  const table = page.locator("table", { has: page.locator("caption", { hasText: "Per-seed result" }) });
  const out: Record<number, { final: number | null; diverged: boolean }> = {};
  for (const r of await table.locator("tbody tr").all()) {
    const c = (await r.locator("td").allInnerTexts()).map((x) => x.trim());
    out[Number(c[0])] = { final: /^-?\d+\.\d+$/.test(c[1]) ? Number(c[1]) : null, diverged: c[2] !== "none" };
  }
  return out;
}

/** Rejection rows shown in the rejection log (this session's stream view): [seed, round, client, raw reason]. */
export async function readRejectionLog(page: Page) {
  await openTableViews(page);
  const table = page.locator("table", { has: page.locator("th", { hasText: /raw reason/i }) }).first();
  const heads = (await table.locator("thead th").allInnerTexts()).map((h) => h.trim().toLowerCase());
  const idx = (re: RegExp) => heads.findIndex((h) => re.test(h));
  const [iR, iS, iC, iW] = [idx(/^round/), idx(/^seed/), idx(/^client/), idx(/raw reason/)];
  const rows: { seed: number | null; round: number; client: number | null; raw: string }[] = [];
  for (const r of await table.locator("tbody tr").all()) {
    const c = (await r.locator("td").allInnerTexts()).map((x) => x.trim());
    rows.push({ seed: iS < 0 ? null : Number(c[iS]), round: Number(c[iR]), client: /^\d+$/.test(c[iC] ?? "") ? Number(c[iC]) : null, raw: c[iW] });
  }
  return rows;
}

/** Run the same config on the backend (no browser) and collect its events: the reference for custom-mode checks. */
export async function backendRun(request: APIRequestContext, body: object) {
  const r = await request.post(`${API}/api/runs`, { data: body });
  expect(r.status()).toBe(201);
  const { id } = await r.json();
  const txt = await (await request.get(`${API}/api/runs/${id}/stream`, { timeout: 230_000 })).text();
  const events = txt.split("\n\n").map((b) => b.replace(/^data: /, "").trim()).filter(Boolean).map((b) => JSON.parse(b));
  return { id: id as string, events };
}
