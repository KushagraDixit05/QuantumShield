# UI QA report (Agent Q)

Date: 2026-10-09. Repo is not a git repo. Nothing in backend/ or frontend/ source was edited.

## What was run (exact commands) and results

| # | Command | Result |
|---|---|---|
| 1 | `.venv/bin/python -m pytest tests/backend -q` | `86 passed, 1 warning in 5.55s` (warning: Starlette deprecation, httpx in TestClient) |
| 2 | `.venv/bin/python -m pytest -q -x --ignore=tests/zk` | `234 passed, 1 warning in 52.41s` |
| 3 | `tests/zk` | NOT RUN. 116 tests collected; the `honest` fixture needs a real RISC Zero proof (about 7 min, 2.4 GB) unless cached, and several tests call `qs-zk prove`. Task rule: never run a prover. |
| 4 | `cd frontend && npm run lint` | clean, no output (eslint exit 0) |
| 5 | `npm run typecheck` | clean (`tsc --noEmit`, exit 0) |
| 6 | `NEXT_PUBLIC_API_URL=http://127.0.0.1:8011 npm run build` | OK: Next 16.4.0 Turbopack, compiled, TypeScript finished, 10/10 static pages; routes `/ /attacks /consensus /limitations /overheads /run /zk` all static |
| 7 | `cd tests/e2e && npx playwright test` | 32 tests: 31 passed, 1 failed (final full run, 1.1 min). The failure is a real defect (D-Q1 below). Run/consensus and screenshot specs were re-run alone afterwards: `9 passed`. |

Setup: Chromium from `~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome` (headless, `--no-sandbox`, via `launchOptions.executablePath`, auto-found in `tests/e2e/playwright.config.ts`). No browser download. No prover. Own backend `127.0.0.1:8011` and production frontend (`next start -p 3001`, built with `NEXT_PUBLIC_API_URL=http://127.0.0.1:8011`), both started and stopped by the Playwright `webServer` config. Ports 8000 and 3000 (someone else's) were not touched; I only killed the one `next-server` I had started by hand on 3001.

CORS finding: backend `main.py:22` allows only localhost/127.0.0.1 on :3000 and :3001. An OPTIONS preflight from `http://127.0.0.1:3011` returned HTTP 400, so 3011 is not usable; tests use 3001.

## E2E tests (tests/e2e/specs)

- `pages.spec.ts`: overview (3 curves drawn, labels A/B/C, "Source:" captions for scenarios.json and scenarios.csv, D-012, DIVERGED); overheads (hardware CPU from `/api/overheads` shown, 4 source captions, REPLAYED); limitations (exactly 19 `li`, source caption, API also 19); attacks (>=2 "DIVERGED 5 of 5" cells with `.qs-diverged-fill`, "attack not stopped: 0 rejected" flag, D-012 note, replay-row note, diverged cell has no `NN.N%`); zk (ReplayedBadge present, 0 `.qs-bigbadge.live`, every receipt label matches `/^replayed from receipt [0-9a-f]{12}, generated .*, on /` and is rendered, all `replayed: true`); POST `/api/runs` with `live_zk:true` is 422 and `/api/health` `live_zk_enabled:false`; per page (7 pages): no console error / pageerror / failed request / HTTP>=400, theme toggle changes and restores background; per page at 390px: `scrollWidth <= clientWidth`.
- `run_consensus.spec.ts`: /run, preset C, seed 0 only, 3 rounds, Run; LIVE badge, run finishes, accuracy/accepted/rejected text, line chart, rejection-log rows labelled "plaintext norm gate (not ZK)" with raw reason `norm_bound_exceeded`; then /consensus, Load, rounds table, click "Verify certificate (public keys only)" -> "valid", "quorum met", "Checked with public keys only".
- `screenshots.spec.ts`: writes docs/screenshots.
- Spot checks against data (no fabricated numbers): overview none/off mean final acc equals mean of the 5 CSV rows (0.9421, computed in the test from `demo/results/scenarios.csv`); scaled/off shows "DIVERGED 5 of 5" and CSV has diverged_round set for all 5 seeds; overheads Ed25519 envelope overhead 94 bytes equals `sig_bench_overhead.csv`. Also observed: curves API seed 0 A final 0.952646 matches CSV 0.9526; the run-page final accuracy 0.8747 (3 rounds) is computed by the backend, not in the CSV (a different round count), so it is not comparable to a stored value.

## Honesty-rule checks

- Sources shown: every card inspected shows a "Source:" caption (overview, overheads, attacks, run, consensus, limitations). PASS.
- No live ZK: no LiveBadge on /zk; "ZK: replay only" chip on every page; `live_zk:true` -> 422; health `live_zk_enabled:false`. PASS.
- Replayed labels: all 4 receipt-backed rows carry the required label; 2 rows (client 4, attacker) have no receipt and show "replayed from stored results (no receipt file...)" with status NO RECEIPT (not verified, not faked). PASS.
- Diverged shown as diverged: heatmap, overview table, overheads latency table and chart (B line stops at round 6 with "B DIVERGED" marker) never show 0.0 as accuracy. PASS.
- Norm gate labelled "plaintext norm gate (not ZK)". PASS.

## Visual review (screenshots in docs/screenshots/: overview, run, zk, consensus, overheads, attacks, limitations, overview-dark, attacks-dark, run-phone)

I viewed overview, attacks-dark, run, run-phone, consensus. zk, overheads, limitations, overview light/attacks light were not visually inspected by me (only via DOM text and passing tests).
- Overview: charts render, B curve stops at the divergence round with shaded region. Defect: legend reads "A: A: benign..." (duplicated id prefix) (D-Q3).
- Attacks (dark): contrast good, hatched diverged cells, flags readable. Minor: hint text "arrow keys are not needed: tab between cells" is awkward.
- Run: accuracy chart has a small visible break in the line between rounds 1 and 2 (single-seed line; unexplained, cosmetic, not investigated). Phone width: no overflow, nav wraps to two rows, readable.
- Full-page screenshots of pages with a sticky header/sidebar show the sidebar and top bar overlaid mid-page (consensus.png, left nav cut off at ~720px in others). This is a Playwright full-page capture artifact of fixed-position elements, not judged a defect.
- Text defects: double period in D-012 notes ("divergence count..", "diverged..") (D-Q4).

## Defects

| id | Severity | Owner | Where | Detail |
|---|---|---|---|---|
| D-Q1 | medium | B1 (parser) or F1 (render) | `backend/limitations.py` returns item text with raw markdown; shown by `frontend/components/LimitationsView.tsx:14` | Limitations page prints literal `**Delta is visible to aggregators.**` etc. Test `limitations: no raw markdown markers leak` fails. Fix: strip/convert `**`/backticks in backend parser or render bold in the view. (Attacks page already strips markdown from the same text.) |
| D-Q2 | low | F2 | `frontend/components/consensus/ConsensusView.tsx:~20-27` | After a run, /consensus pre-fills the run id but does not load it; the user must press Load (an empty page otherwise). Consider auto-loading the remembered id. |
| D-Q3 | low | F1 | `frontend/components/overview/CurvesChart.tsx` legend / label source | Legend labels "A: A: benign, no attack" (id prefix duplicated; the API label already starts with the id). |
| D-Q4 | low | F1 | `frontend/components/shared/DivergedMarker.tsx:19` | `DivergedNote` appends "." to text that already ends with a period, giving ".." on overview and attacks. |
| D-Q5 | info | lead | `docs/api_contract.md` | CORS allows only 3000/3001; 3011 refused (HTTP 400). Not a bug, but ports are fixed. |
| D-Q6 | info | F2 | `/run` | Playwright reports `net::ERR_ABORTED` for the SSE `/stream` request when the page is navigated away or the EventSource is closed (`client.ts:90-96`). Benign; the e2e test filters exactly this message for the run test only. |

## Unverified

- tests/zk (prover required; not run). No real or dev-mode ZK proof was generated.
- Run with more seeds/rounds, scenarios A/B and custom attack/defence, aggregators other than fedavg through the UI (backend tests cover the runner).
- Stored-rejection view toggle and receipts cards on /zk beyond text presence; hover/tooltips on the heatmap; keyboard navigation.
- Contrast was judged by eye on 3 screenshots only, not measured. No cross-browser (Chromium only). No Lighthouse/a11y audit.
- Certificate verify tested only on round 0 of a benign-honest-node run; tampered certificate in UI not tested (backend tests cover it).

## ui-test Makefile target

Works with this layout provided `cd tests/e2e && npm install` has been run once (node_modules is not committed). Suggested change: add `cd tests/e2e && npm install` to `ui-install` (it currently only installs frontend). The target's `npm run build` in frontend uses the default API URL (8000); the Playwright config rebuilds with `NEXT_PUBLIC_API_URL=http://127.0.0.1:8011` (overwrites `.next`), so the build step in the target is just a build check. The config starts and stops both servers itself (`reuseExistingServer:false`, so it fails fast if 8011/3001 are taken) and never touches 8000/3000. With the current known defect D-Q1 `npx playwright test` exits non-zero until it is fixed.

## Lead follow-up (after Q's run)
Fixed D-Q1 (raw `**` on /limitations), D-Q2 (consensus now auto-loads the remembered run), D-Q3 (duplicated "A: A:" legend, also in the run page scenario list) and D-Q4 (".." after the D-012 note). Changed the e2e radio selector to match the corrected label. Re-ran `make ui-test`: backend 86 passed; frontend lint, typecheck and build clean; Playwright 30 passed, 0 failed (exit 0).
Receipt "generated" dates are the files' mtimes in UTC (2026-10-08T19:18 to 19:45), as shown on /zk.

## Gaps run (presets, custom/multi-seed, certificates, OpenAPI types, screenshot review)
`make ui-test` (exit 0): `pytest tests/backend tests/hardening` 106 passed; `check:api` OK; frontend lint, typecheck, build clean; Playwright 47 passed, 0 failed, 0 skipped (30 earlier smoke/screenshot specs + 17 below). Chromium from `~/.cache/ms-playwright` (`/opt/pw-browsers` does not exist). No proof was run; no `live_zk`.

| Check | Agent | Count |
|---|---|---|
| Presets A, B, C numeric checks vs `scenarios.json/csv`, `rejections.csv` (`tests/e2e/presets/`) | P | 3 |
| Custom mode vs backend run and vs stored CSV; multi-seed per-seed finals, mean/std vs CSV, Overview table, heatmap; diverged seeds (`tests/e2e/custom_multiseed/`) | C | 10 |
| Certificates in the UI: untouched accepted, routed-through control, tampered signature rejected, fewer than 3 votes (`tests/e2e/certificates/`) | X | 4 |
| Certificate backend cases: 20 pytest tests (`tests/hardening/test_certificates.py`) | X | 20 (pytest) |
| OpenAPI types generated, hand types alias `schema.d.ts`, stale-schema check `npm run check:api` (shown to fail on a stale scratch copy) | G | 1 gate |
| Screenshot review of overview, attacks, zk, overheads, limitations (`docs/screenshot_review.md`) | S | review |
| Shared config/fixtures/helpers (`tests/e2e/shared/`), `docs/e2e_map.md`, Makefile, merge fixes | Lead | |

Honest notes: the preset B check and map were corrected (run stops at divergence), see docs/ui_issues.md "Lead resolution". Std is population std everywhere. The heatmap prints 1-decimal percentages, so its comparison is at 0.05 pp. The run page has no mean ± std line (UI-G-1); the check recomputes it from displayed per-seed values. The UI can only verify stored certificates, so tampering is done by intercepting the verify request with `page.route`. Screenshots were regenerated before review, then the Overheads page changed (S-3/S-5/S-6 fixes) and the final `make ui-test` regenerated them; `docs/screenshot_review.md` describes the pre-fix overheads image. Dark variants and the header theme-button label were not reviewed.
