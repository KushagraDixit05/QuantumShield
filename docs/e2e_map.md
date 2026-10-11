# e2e map: what each check reads, what it must match

Every check compares a number or label shown in the UI with its source file or with the backend. Expected values are
loaded from the source at test time (`tests/e2e/shared/data.ts`); none are typed into a test. A check that cannot find
its UI element or its source **fails**; it never skips. No check may loosen a tolerance below to pass.

Runs use the e2e backend on :8011 and a production Next build on :3001 (`tests/e2e/shared/config.ts`). No proof is
ever started (`live_zk` is never sent). Chromium comes from `~/.cache/ms-playwright` (`/opt/pw-browsers` does not
exist here); `playwright install` is never run.

## Facts the checks rely on
- Presets (`demo/run_demo.py:158`, labels `demo/plot.py:23`): A = attack none / defence off, B = scaled / off, C = scaled / on. Config `configs/demo.yaml` -> `configs/mvp.yaml`, 10 rounds.
- `demo/results/scenarios.json`: `all["<attack>/<defence>"]` = seed-0 curve, 11 values; index 0 is the untrained model, **round r = index r+1**. Values rounded to 6 dp. After divergence the stored values are `0.0` (D-012 convention): the UI must show DIVERGED there, never 0.
- `demo/results/scenarios.csv`: one row per attack/defence/seed (seeds 0-4), `final_acc` at 4 dp, `diverged_round` blank if none.
- `demo/results/rejections.csv`: `attack,defence,seed,round,client,reason` for the 10-round runs.
- The UI prints accuracies with `toFixed(4)` (`frontend/lib/format.ts`).
- The run page shows per-round accuracy per seed, per-seed final accuracy, accepted/rejected counts and the rejection log. It does **not** show a mean ± std over the chosen seeds. Mean ± std is shown on Overview (`SummaryTable`, population std (n), as in `scenarios_summary.md`, non-diverged seeds only) and on the attack heatmap (all 5 stored seeds). See "Known gap" below.

## Tolerances
| Name | Value | Used for |
|---|---|---|
| `TOL_EXACT` | 1e-9 | UI 4-dp value vs CSV 4-dp value; UI vs backend event rounded the same way |
| `TOL_DISPLAY_VS_6DP` | 0.00005 + 1e-9 | UI 4-dp value vs 6-dp stored curve value |
| counts, rounds, clients, reason strings | exact | accepted/rejected counts, rejection rows |
| mean / std | recomputed from the displayed per-seed values, compared at 4 dp with `TOL_DISPLAY_VS_6DP` | mean ± std checks |

## Presets (Agent P, `tests/e2e/presets/`)
| Check | UI element read | Must match | Tolerance |
|---|---|---|---|
| Preset A, seed 0, 10 rounds: per-round accuracy | per-round table, column `seed 0` | `scenarios.json` `all["none/off"][r+1]` | `TOL_DISPLAY_VS_6DP` |
| Preset A final accuracy | "Per-seed result" table | `scenarios.csv` none/off seed 0 `final_acc` | `TOL_EXACT` |
| Preset A no divergence, no rejections | DIVERGED markers; rejection log rows | `diverged_round` blank; `rejected` = 0 and no `rejections.csv` rows for none/off seed 0 | exact |
| Preset B per-round accuracy up to divergence | per-round table | `scenarios.json` `all["scaled/off"][r+1]` for rounds before `diverged_round` | `TOL_DISPLAY_VS_6DP` |
| Preset B divergence | DIVERGED marker at the round the CSV gives; D-012 note text; per-seed table | `scenarios.csv` scaled/off seed 0 `diverged_round` (6); that round shows DIVERGED, **not** 0.0000. The run stops there (`run_demo.run_scenario` returns), so rounds 7-9 are not listed; the stored 0.0 for them is the D-012 convention, not a run | exact round |
| Preset C (regression of the existing check, with numbers) | per-round table, per-seed table, rejection log | `scenarios.json` `all["scaled/on"]`, `scenarios.csv` scaled/on seed 0, `rejections.csv` rows for scaled/on seed 0 (round, client, reason) | as above; rejection rows exact as a set |
| Accepted/rejected counts per round | counts chart table | accepted = clients - rejected rows in that round (`rejections.csv`), clients = 5. A diverged round has no counts (divergence happens during local training, before consensus): both cells read `n/a` | exact |

## Custom mode and multi-seed (Agent C, `tests/e2e/custom_multiseed/`)
| Check | UI element read | Must match | Tolerance |
|---|---|---|---|
| Custom attack x defence x aggregator (at least: forged/on/fedavg, scaled/on/norm_filter, replay/on/median; rounds 5) | per-round table, per-seed table, rejection log | the same config run through `POST /api/runs` + `/stream` by the test (`shared/runner.ts backendRun`), per round and per seed | `TOL_EXACT` (same backend values, same rounding) |
| Custom config equals stored result where one exists (forged/on and replay/on, fedavg, 10 rounds, seed 0) | per-seed table, rejection log | `scenarios.csv`, `rejections.csv` | `TOL_EXACT`; rejections as a set |
| Multi-seed (seeds 0,1,2 on A, then C) | per-seed table: one row per chosen seed, per-round table: one column per seed | `scenarios.csv` `final_acc` per seed; `scenarios.json` for seed 0 | `TOL_EXACT` |
| Mean ± std over the chosen seeds | mean and std recomputed from the displayed per-seed finals; for all 5 seeds also the Overview summary table and the heatmap cell | `scenarios.csv` rows for that attack/defence; Overview `std (population, n)`, heatmap uses the backend `attack_matrix` | `TOL_DISPLAY_VS_6DP` |
| Diverged seeds in a multi-seed run (B, seeds 0-2, 10 rounds) | per-seed table | `scenarios.csv` `diverged_round` per seed; mean excludes diverged seeds | exact round |

**Known gap (not fixed here; no new features):** the run page has no mean ± std line. The multi-seed check therefore
recomputes it from the displayed per-seed values and compares it with the stored CSV and with the Overview/heatmap
values. Recorded in `docs/ui_issues.md` (UI-G-1).

## OpenAPI types (Agent G, `frontend/lib/api/`, Makefile)
| Check | Reads | Must match |
|---|---|---|
| Stale-schema | `docs/openapi.json` exported fresh from `backend.main:app` (`python -m backend.export_openapi` to a temp file) vs the committed `docs/openapi.json`; `openapi-typescript` output to a temp file vs `frontend/lib/api/schema.d.ts` | byte-identical; `make ui-test` fails with a message telling you to run `make ui-gen` otherwise |
| Types alias schema | `frontend/lib/api/types.ts` | response/request interfaces are `components["schemas"][...]` aliases; `npm run typecheck` passes |

## Certificates (Agent X, `tests/e2e/certificates/`, `tests/hardening/`)
| Check | Source | Must match |
|---|---|---|
| Unmodified certificate accepted via the UI | button "Verify certificate (public keys only)" on `/consensus` after a C run | result text "valid", "quorum met", "Checked with public keys only"; equals `POST /api/certificates/verify` for the same run/round |
| Modified certificate rejected via the UI | the UI only verifies the stored certificate, so the test intercepts the button's `POST /api/certificates/verify` with `page.route` and substitutes a copy of `GET /api/certificates/{run}/{round}` with one vote's signature flipped | UI shows invalid and the failing vote; backend returns `valid: false` for the same body |
| Other tampers (payload hash, fewer than 3 votes, duplicated voter, wrong round, vote from unknown node) | same | `valid: false`, `quorum_met` as appropriate |
| Backend direct tests | `tests/hardening/test_certificates.py` | same cases without the browser; secret keys are never read |

## Screenshot review (Agent S, `docs/screenshot_review.md`)
Five screenshots: `overview.png`, `attacks.png`, `zk.png`, `overheads.png`, `limitations.png` (the five not viewed in the first QA pass). Each is opened with Read; each entry states what is visible, whether numbers match the source file named on the page, and any live/replayed labelling problem. Only what is visible in the image is described.
