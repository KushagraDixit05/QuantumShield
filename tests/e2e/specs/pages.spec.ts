import { test, expect, PAGES, settle, readCsv, API } from "./fixtures";

test("overview: A/B/C curves, Source caption, D-012, values match CSV", async ({ page, problems }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Does the defence hold?" })).toBeVisible();
  await expect(page.getByText("A: benign, no attack").first()).toBeVisible();
  await expect(page.getByText("B: poisoned, plain FedAvg").first()).toBeVisible();
  await expect(page.getByText("C: poisoned, QuantumShield on").first()).toBeVisible();
  await expect(page.getByText(/Source: demo\/results\/scenarios\.json/).first()).toBeVisible();
  await expect(page.getByText(/Source: demo\/results\/scenarios\.csv/).first()).toBeVisible();
  await expect(page.getByText(/DIVERGED/).first()).toBeVisible();
  await expect(page.getByText(/D-012/).first()).toBeVisible();
  // 3 curves drawn (recharts line paths)
  expect(await page.locator("svg .recharts-line-curve").count()).toBeGreaterThanOrEqual(3);

  // spot check 1: mean final accuracy of none/off over 5 seeds, computed from the CSV
  const rows = readCsv("demo/results/scenarios.csv").filter((r) => r.attack === "none" && r.defence === "off");
  const mean = rows.reduce((s, r) => s + Number(r.final_acc), 0) / rows.length;
  const row = page.locator("tr", { hasText: "none" }).filter({ hasText: "off" }).first();
  await expect(row).toContainText(mean.toFixed(4));
  // spot check 2: scaled/off is 5 of 5 diverged in CSV and shown as diverged, with no accuracy
  const sc = readCsv("demo/results/scenarios.csv").filter((r) => r.attack === "scaled" && r.defence === "off");
  expect(sc.every((r) => r.diverged_round !== "")).toBe(true);
  await expect(page.locator("tr", { hasText: "scaled" }).filter({ hasText: "off" }).first()).toContainText(/DIVERGED 5 of 5/);
  expect(problems).toEqual([]);
});

test("overheads: hardware specs, source captions, CSV-backed numbers", async ({ page, problems }) => {
  await page.goto("/overheads");
  await settle(page);
  const oh = await (await page.request.get(`${API}/api/overheads`)).json();
  await expect(page.getByText(/Ed25519/).first()).toBeVisible();
  await expect(page.getByText(/ML-DSA-65/).first()).toBeVisible();
  for (const f of ["sig_bench.csv", "sig_bench_overhead.csv", "sig_bench_throughput.csv", "zk_bench.csv"])
    await expect(page.getByText(new RegExp(`Source: .*${f}`)).first()).toBeVisible();
  await expect(page.getByText(/REPLAYED/).first()).toBeVisible();
  // hardware specs: from API, must be on the page
  const hw = oh.hardware;
  expect(hw.cpu).toBeTruthy();
  await expect(page.getByText(hw.cpu, { exact: false }).first()).toBeVisible();
  await expect(page.getByText(/12 threads|threads/i).first()).toBeVisible();
  // spot check 3: Ed25519 envelope overhead bytes (94) from CSV appears in its row
  const ed = readCsv("demo/results/sig_bench_overhead.csv").find((r) => r.config === "Ed25519")!;
  await expect(page.locator("tr:visible", { hasText: "Ed25519" }).filter({ hasText: ed.envelope_overhead_bytes }).first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("limitations: 19 items with sources", async ({ page, problems }) => {
  await page.goto("/limitations");
  await settle(page);
  await expect(page.locator("ol.qs-limits > li")).toHaveCount(19);
  await expect(page.getByText(/Source: docs\/limitations\.md/)).toBeVisible();
  const api = await (await page.request.get(`${API}/api/limitations`)).json();
  expect(api.sections.flatMap((s: { items: unknown[] }) => s.items)).toHaveLength(19);
  expect(problems).toEqual([]);
});

test("limitations: no raw markdown markers leak into the text (defect check)", async ({ page }) => {
  await page.goto("/limitations");
  await settle(page);
  const txt = await page.locator("ol.qs-limits").first().innerText();
  expect(txt, "raw ** markdown shown to the user").not.toContain("**");
});

test("attacks: heatmap cells, diverged markers, D-012 and replay notes", async ({ page, problems }) => {
  await page.goto("/attacks");
  await settle(page);
  await expect(page.getByText("Attack by defence: final accuracy")).toBeVisible();
  const diverged = page.getByText(/DIVERGED 5 of 5/);
  expect(await diverged.count()).toBeGreaterThanOrEqual(2); // scaled/off and forged/off
  expect(await page.locator(".qs-diverged-fill").count()).toBeGreaterThanOrEqual(2);
  await expect(page.getByText(/ATTACK NOT STOPPED: 0 REJECTED/i).first()).toBeVisible();
  await expect(page.getByText(/D-012/).first()).toBeVisible();
  await expect(page.getByText(/Replay row \(limitation 10\)/)).toBeVisible();
  await expect(page.getByText(/Source: /).first()).toBeVisible();
  // diverged cells must not print an accuracy percentage as if measured
  const cell = page.locator(".qs-diverged-fill").first();
  await expect(cell).not.toContainText(/\d+\.\d%/);
  // 8 cells
  const m = await (await page.request.get(`${API}/api/results/attack_matrix`)).json();
  expect(JSON.stringify(m)).toContain("diverged");
  expect(problems).toEqual([]);
});

test("zk: ReplayedBadge, replayed label for every receipt, no LiveBadge", async ({ page, problems }) => {
  await page.goto("/zk");
  await settle(page);
  await expect(page.getByText("REPLAYED").first()).toBeVisible();
  expect(await page.locator(".qs-bigbadge.live").count()).toBe(0);
  await expect(page.locator(".qs-bigbadge.replayed").first()).toBeVisible();
  const z = await (await page.request.get(`${API}/api/zk/rounds`)).json();
  const withReceipt = z.rounds.filter((r: { receipt_id: string | null }) => r.receipt_id);
  expect(withReceipt.length).toBeGreaterThanOrEqual(4);
  const re = /^replayed from receipt [0-9a-f]{12}, generated .*, on /;
  for (const r of withReceipt) {
    expect(r.label).toMatch(re);
    expect(r.replayed).toBe(true);
    await expect(page.getByText(r.label, { exact: true }).first()).toBeVisible();
  }
  for (const r of z.rounds) expect(r.replayed).toBe(true);
  await expect(page.getByText("✓ VERIFIED").first()).toBeVisible();
  await expect(page.getByText(/NO RECEIPT/i).first()).toBeVisible();
  // No live-ish wording
  expect(await page.getByText(/^LIVE$/).count()).toBe(0);
  expect(problems).toEqual([]);
});

test("API: POST /api/runs with live_zk true is 422", async ({ request }) => {
  const r = await request.post(`${API}/api/runs`, { data: { scenario: "C", seeds: [0], rounds: 1, live_zk: true } });
  expect(r.status()).toBe(422);
  const h = await (await request.get(`${API}/api/health`)).json();
  expect(h.live_zk_enabled).toBe(false);
});

for (const p of PAGES) {
  test(`no console errors / failed requests, both themes render: ${p}`, async ({ page, problems }) => {
    await page.goto(p);
    await settle(page);
    await page.waitForTimeout(500);
    const main = page.locator("main");
    await expect(main).toBeVisible();
    expect((await main.innerText()).length).toBeGreaterThan(100);
    const bg = async () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const before = await bg();
    const initial = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    await page.getByRole("button", { name: /Switch to (dark|light) theme/ }).click();
    const after = await bg();
    expect(after, `theme toggle changes background on ${p} (initial ${initial})`).not.toBe(before);
    await page.getByRole("button", { name: /Switch to (dark|light) theme/ }).click();
    expect(await bg()).toBe(before);
    expect(problems).toEqual([]);
  });

  test(`phone width 390px has no horizontal page scroll: ${p}`, async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 800 } });
    const page = await ctx.newPage();
    await page.goto(p);
    await settle(page);
    await page.waitForTimeout(500);
    const { sw, cw } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    expect(sw, `scrollWidth ${sw} > clientWidth ${cw}`).toBeLessThanOrEqual(cw);
    await ctx.close();
  });
}
