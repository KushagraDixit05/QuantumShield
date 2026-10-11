# Agent P: presets A, B, C e2e (tests/e2e/presets/)

Run: `cd tests/e2e && npx playwright test presets/` (own servers 8011/3001). Last result: **2 passed, 1 failed** (A pass, C pass, B fail on real defects).

## Done
Files: `tests/e2e/presets/common.ts` (helpers, imports only ../shared), `preset_a.spec.ts`, `preset_b.spec.ts`, `preset_c.spec.ts`. All expected values are read from demo/results at test time (scenarios.json, scenarios.csv, rejections.csv). Each test also asserts the `problems` fixture is empty (only SSE_ABORT filtered). No proof, no live_zk, no skips, no tolerance loosening.

Checks (one UI run each, seed 0, 10 rounds):
- `preset A (none/off), seed 0, 10 rounds matches demo/results` (PASS): per-round table seed 0 vs `all["none/off"][r+1]` (TOL_DISPLAY_VS_6DP); per-seed final vs scenarios.csv final_acc (TOL_EXACT); diverged_round blank and per-seed "none", no `.qs-diverged` markers; csv rejected = 0 and 0 rejections.csv rows, rejection log empty ("No rejections received yet"); counts table 10 rows, accepted = 5 - rejected.
- `preset B (scaled/off), seed 0, 10 rounds diverges where the CSV says` (FAIL): rounds before diverged_round (6) vs `all["scaled/off"][r+1]`; rounds from there show DIVERGED, no number, no "0.0000"; per-seed cell "DIVERGED at round 6" and "from round 6"; D-012 note visible, contains /convention, not a measured accuracy/ and "seed 0 diverged at round 6"; no "0.0000" in any table cell; counts check. Failures (all real, see ui_issues): UI-G-P-1 (only 7 of 10 rounds listed, in both tables), UI-G-P-2 (round 6 accepted 0, expected 5). The numeric checks, DIVERGED marker, per-seed row and D-012 note pass.
- `preset C (scaled/on), seed 0, 10 rounds: numeric regression against demo/results` (PASS): per-round vs `all["scaled/on"]`, final vs csv, no divergence, rejection log rows (seed|round|client|raw reason) equal rejections.csv rows as a set (10 rows), counts accepted = 5 - rejected.

Output: `3 tests: 2 passed, 1 failed` (preset_b.spec.ts: soft failures "per-round table ... Expected 10 Received 7", "counts table ... Expected 10 Received 7", "round 6 accepted Expected 5 Received 0").

## Blocked
Nothing.

## Needs (lead-owned shared/ and config)
- `shared/runner.ts` readers (`readAccuracyTable`, `readPerSeedResults`, `readRejectionLog`, counts) cannot work as written: (1) the per-round and counts tables are inside a collapsed `<details><summary>Table view</summary>`, so `innerText` is empty until opened; (2) CSS uppercases headers, so `innerText` heads are "ROUND", "SEED 0" and `/^seed (\d+)/` never matches. I worked around both locally in `presets/common.ts` (open the details; compare lowercased heads). Please fix in shared, then the local copies can go.
- Early in the session `npm run build` failed on a type error in `frontend/components/consensus/ConsensusView.tsx(145,58)` (another agent's edit in progress); it cleared by itself.

## Real bugs found
UI-G-P-1, UI-G-P-2 (preset B), UI-G-P-3 (note wording) in docs/ui_issues.md.
