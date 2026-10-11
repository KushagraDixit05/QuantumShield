// Certificate verification through the UI, compared with POST /api/certificates/verify. Imports only ../shared.
// LIMITATION: the UI can only verify the stored certificate of a round (button "Verify certificate (public keys only)"
// posts {run_id, round}); it has no way to edit or paste a certificate. The tampered case therefore intercepts that one
// POST with page.route and substitutes {certificate: <GET copy with one vote's signature flipped>}. This tests that the
// UI renders what the backend says for a bad certificate, not that a user could tamper through the UI.
import type { APIRequestContext, Page } from "@playwright/test";
import { API, expect, settle, SSE_ABORT, test } from "../shared/fixtures";
import { choosePreset, runAndWait, setSeeds } from "../shared/runner";

const ROUNDS = 3;
const VERIFY = /\/api\/certificates\/verify$/;
const BTN = "Verify certificate (public keys only)";

type Checked = { node: number; ok: boolean; reason: string };
type Verdict = { valid: boolean; quorum_met: boolean; checked: Checked[]; public_keys_only: boolean };

async function runCAndOpenConsensus(page: Page) {
  await page.goto("/run");
  await settle(page);
  await choosePreset(page, "C");
  await setSeeds(page, [0]);
  await runAndWait(page, ROUNDS);
  const runId = (await page.locator("code.mono").first().innerText()).trim();
  expect(runId.length).toBeGreaterThan(4);
  await page.getByRole("link", { name: "Consensus" }).first().click();
  await expect(page).toHaveURL(/\/consensus/);
  await expect(page.getByRole("textbox", { name: "Run id" })).toHaveValue(runId);
  await page.getByRole("button", { name: "Load", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Rounds" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: BTN })).toHaveCount(ROUNDS);
  return runId;
}

const roundItem = (page: Page, n: number) => page.locator("ol > li").filter({ hasText: new RegExp(`round ${n}\\b`) });

async function getCert(request: APIRequestContext, runId: string, rnd: number) {
  const r = await request.get(`${API}/api/certificates/${runId}/${rnd}`);
  expect(r.status()).toBe(200);
  return await r.json();
}
async function backendVerify(request: APIRequestContext, body: object): Promise<Verdict> {
  const r = await request.post(`${API}/api/certificates/verify`, { data: body });
  expect(r.status(), "verify must answer 200 even for a tampered certificate").toBe(200);
  return await r.json();
}

/** What the UI shows inside one round's result block, parsed into the same shape as the API verdict. */
async function readUi(page: Page, rnd: number) {
  const item = roundItem(page, rnd);
  const status = item.getByRole("status").filter({ hasText: /Checked with public keys only/ });
  await expect(status).toBeVisible({ timeout: 30_000 });
  const text = await status.innerText();
  const valid = /✓ valid/i.test(text) && !/not valid/i.test(text);
  expect(valid || /✗ not valid/i.test(text), `round ${rnd}: neither valid nor not valid shown:\n${text}`).toBeTruthy();
  const quorum_met = /quorum met/i.test(text) && !/quorum not met/i.test(text);
  expect(quorum_met || /quorum not met/i.test(text), `round ${rnd}: no quorum badge:\n${text}`).toBeTruthy();
  const checked: Checked[] = [];
  for (const tr of await status.locator("table tbody tr").all()) {
    const c = (await tr.locator("td").allInnerTexts()).map((x) => x.trim());
    checked.push({ node: Number(c[0]), ok: /✓ ok/i.test(c[1]), reason: c[2] });
  }
  return { valid, quorum_met, checked, text };
}

test("(a) untouched certificates: UI valid + quorum met on every round, equal to the backend verdict", async ({ page, request, problems }) => {
  const runId = await runCAndOpenConsensus(page);
  for (let rnd = 0; rnd < ROUNDS; rnd++) {
    await roundItem(page, rnd).getByRole("button", { name: BTN }).click();
    const ui = await readUi(page, rnd);
    expect(ui.valid, `round ${rnd} UI valid`).toBe(true);
    expect(ui.quorum_met, `round ${rnd} UI quorum`).toBe(true);
    await expect(roundItem(page, rnd).getByText(/Checked with public keys only: no secret key is used/)).toBeVisible();
    const be = await backendVerify(request, { certificate: await getCert(request, runId, rnd) });
    expect(be.public_keys_only).toBe(true);
    expect({ valid: ui.valid, quorum_met: ui.quorum_met, checked: ui.checked }, `round ${rnd}: UI vs backend`)
      .toEqual({ valid: be.valid, quorum_met: be.quorum_met, checked: be.checked });
    expect(be.valid && be.quorum_met).toBe(true);
    expect(be.checked.length).toBe(4);
    // the stored-round form (what the button posts) gives the same verdict as the pasted certificate
    expect(await backendVerify(request, { run_id: runId, round: rnd })).toEqual(be);
  }
  expect(problems.filter((x) => !SSE_ABORT.test(x))).toEqual([]);
});

test("(b) control: the button's request passed through page.route unchanged is still valid", async ({ page, request, problems }) => {
  const runId = await runCAndOpenConsensus(page);
  let intercepted = 0;
  await page.route(VERIFY, async (route) => {
    intercepted++;
    expect(route.request().method()).toBe("POST");
    expect(JSON.parse(route.request().postData() ?? "{}")).toEqual({ run_id: runId, round: 1 });
    await route.continue();
  });
  await roundItem(page, 1).getByRole("button", { name: BTN }).click();
  const ui = await readUi(page, 1);
  expect(intercepted, "the route handler must have seen the button's POST").toBe(1);
  const be = await backendVerify(request, { run_id: runId, round: 1 });
  expect({ valid: ui.valid, quorum_met: ui.quorum_met, checked: ui.checked }).toEqual({ valid: be.valid, quorum_met: be.quorum_met, checked: be.checked });
  expect(ui.valid && ui.quorum_met).toBe(true);
  // control 2: replacing the body with the untouched GET certificate (the substitution mechanism itself) is also valid
  await page.unroute(VERIFY);
  await page.route(VERIFY, (route) => route.continue({ postData: JSON.stringify({ certificate: untouched }), headers: { ...route.request().headers(), "content-type": "application/json" } }));
  const untouched = await getCert(request, runId, 2);
  await roundItem(page, 2).getByRole("button", { name: BTN }).click();
  const ui2 = await readUi(page, 2);
  expect(ui2.valid && ui2.quorum_met, "substituted-but-untouched certificate must be valid").toBe(true);
  expect(problems.filter((x) => !SSE_ABORT.test(x))).toEqual([]);
});

test("(c) tampered: one vote's signature flipped (substituted via page.route) is shown invalid, naming the vote; backend agrees", async ({ page, request, problems }) => {
  const runId = await runCAndOpenConsensus(page);
  const FLIP_NODE = 2;
  const cert = await getCert(request, runId, 1);
  const vote = cert.votes.find((v: { node: number }) => v.node === FLIP_NODE);
  const sig: string = vote.sigs[0].sig;
  vote.sigs[0].sig = sig.slice(0, -2) + (sig.slice(-2) === "00" ? "ff" : "00");
  expect(vote.sigs[0].sig).not.toBe(sig);
  const body = { certificate: cert };

  await page.route(VERIFY, (route) =>
    route.continue({ postData: JSON.stringify(body), headers: { ...route.request().headers(), "content-type": "application/json" } }));
  const respPromise = page.waitForResponse((r) => VERIFY.test(r.url()) && r.request().method() === "POST");
  await roundItem(page, 1).getByRole("button", { name: BTN }).click();
  const resp = await respPromise;
  expect(resp.status(), "tampered verify should answer 200 with valid=false, not a 4xx").toBe(200);
  const wire = (await resp.json()) as Verdict;
  expect(JSON.parse(resp.request().postData() ?? "{}")).toEqual(body);   // the substitution reached the wire

  const ui = await readUi(page, 1);
  const be = await backendVerify(request, body);
  expect(be.valid, "backend: tampered certificate is invalid").toBe(false);
  expect(wire).toEqual(be);                                              // browser got the same verdict a direct call gets
  expect(ui.valid, "UI must show not valid").toBe(false);
  await expect(roundItem(page, 1).getByText(/✗ not valid/i)).toBeVisible();
  expect({ valid: ui.valid, quorum_met: ui.quorum_met, checked: ui.checked }).toEqual({ valid: be.valid, quorum_met: be.quorum_met, checked: be.checked });
  // the failing vote is named: node 2 rejected with its reason, the other three ok
  const bad = ui.checked.filter((c) => !c.ok);
  expect(bad.map((c) => c.node)).toEqual([FLIP_NODE]);
  expect(bad[0].reason).toBe("bad_signature");
  expect(ui.checked.filter((c) => c.ok).length).toBe(3);
  const failRow = roundItem(page, 1).getByRole("status").locator("tbody tr").filter({ has: page.getByText(/✗ rejected/i) });
  await expect(failRow).toHaveCount(1);
  await expect(failRow.locator("td").nth(0)).toHaveText(String(FLIP_NODE));
  await expect(failRow.locator("td").nth(2)).toHaveText("bad_signature");
  // the other rounds stay unverified (nothing leaked into them)
  await expect(roundItem(page, 0).getByText(/Checked with public keys only/)).toHaveCount(0);
  // the deliberate tamper produced no HTTP error, console error or failed request
  expect(problems.filter((x) => !SSE_ABORT.test(x))).toEqual([]);
});

test("(d) tampered: fewer than 3 votes (substituted via page.route) is shown as quorum not met; backend agrees", async ({ page, request, problems }) => {
  const runId = await runCAndOpenConsensus(page);
  const cert = await getCert(request, runId, 0);
  cert.votes = cert.votes.slice(0, 2);
  const body = { certificate: cert };
  await page.route(VERIFY, (route) =>
    route.continue({ postData: JSON.stringify(body), headers: { ...route.request().headers(), "content-type": "application/json" } }));
  await roundItem(page, 0).getByRole("button", { name: BTN }).click();
  const ui = await readUi(page, 0);
  const be = await backendVerify(request, body);
  expect(be.valid).toBe(false);
  expect(be.quorum_met).toBe(false);
  expect({ valid: ui.valid, quorum_met: ui.quorum_met, checked: ui.checked }).toEqual({ valid: be.valid, quorum_met: be.quorum_met, checked: be.checked });
  await expect(roundItem(page, 0).getByText(/quorum not met/i)).toBeVisible();
  expect(problems.filter((x) => !SSE_ABORT.test(x))).toEqual([]);
});
