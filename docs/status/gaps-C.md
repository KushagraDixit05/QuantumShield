# Agent C status: custom mode and multi-seed (tests/e2e/custom_multiseed/)

## Done
Files: `util.ts` (local helpers), `custom.spec.ts` (5 tests), `multiseed.spec.ts` (5 tests), `local.config.ts` (debug config, reuses servers already on 8011/3001; not matched by the main config).
Every test also asserts the `problems` fixture is empty (only SSE_ABORT filtered). No proof, no live_zk, no skips, no loosened tolerance.

Checks:
1. custom forged/on/fedavg, 5 rounds, seed 0: UI per-round, per-seed, rejection rows (seed|round|client|raw reason) == backendRun events (TOL_EXACT)
2. custom scaled/on/norm_filter, 5 rounds: same
3. custom replay/on/median, 5 rounds: same
4. custom forged/on/fedavg, 10 rounds: per-seed final/diverged vs scenarios.csv, rejection rows vs rejections.csv, plus backend comparison
5. custom replay/on/fedavg, 10 rounds: same
6. multi-seed preset A seeds 0,1,2: finals vs csv, 3 columns, 3 chart lines/legend entries, seed 0 vs scenarios.json, mean/std from displayed finals vs csv
7. multi-seed preset C seeds 0,1,2: same
8. multi-seed preset B seeds 0,1,2: diverged_round per seed vs csv, no number for diverged seeds (all 3 diverge, so no accuracy enters a mean), DIVERGED at the csv round for seed 0 (stream stops at that round, so the table ends there), D-012 note
9. 5-seed preset A vs Overview summary table (mean, std n-1, seeds)
10. 5-seed preset A vs attack heatmap cell (mean, std at 0.05 pt display resolution)

## Test output
Official command `cd tests/e2e && npx playwright test custom_multiseed/`: could NOT complete (see Blocked).
Run with `-c custom_multiseed/local.config.ts` against the same servers/build (8011/3001): **9 passed, 1 failed (26 s)**.
Failure: test 10, `heatmap std (%): UI 1.4 vs expected 1.619422736656492` (real defect UI-G-C-1).

## Blocked
- Port 8011/3001 are held by orphaned servers from my own first run (that run was killed by my `timeout` because of UI-G-C-2; Playwright does not stop webServers when killed). The permission classifier denied `kill`/`pkill`, so the official command now stops with "http://127.0.0.1:8011/api/health is already used". Lead: kill pids of `uvicorn ... --port 8011` and `next start -p 3001` (or free them), then rerun the official command.

## Needs from lead (shared/ is lead-owned)
- `runner.ts chooseCustom`: selectors broken (UI-G-C-2). Suggested: `page.locator("label:has(select)", { hasText: /^Attack/ }).locator("select")` and the same for `/^Defence/`, `/^Aggregator/`. Until then specs import `chooseCustomLocal` from `./util`.
- Optional: `reuseExistingServer: !process.env.CI` would avoid the stuck-port situation.

## Real defects (also in docs/ui_issues.md)
- UI-G-C-1 heatmap std is population std (pstdev, 1.4%) while Overview shows sample std (1.62 pts); unlabeled. Test 10 fails honestly.
- UI-G-C-2 chooseCustom selectors cannot find the Attack/Defence selects.
- UI-G-1 recorded (no mean ± std on /run).
