# UI F2 status (interactive screens)

## Done
- `/run`: `components/scenario/` (RunView, RejectionLog, reasons). Preset A/B/C or custom attack/defence, attack on/off toggle (off sends attack none), seeds 1-5, aggregator and rounds from /api/scenarios, POST /api/runs then `streamRun`. States idle/submitting/queued/running/done/error. LiveBadge on live output. Accuracy line per seed (null never plotted, DIVERGED reference line + D-012 note), stacked accepted/rejected per round (seed selector), per-seed result table, table views. EventSource closed on unmount and on "Stop watching" (there is no cancel endpoint; backend finishes the run). `live_zk` is never sent; fixed "ZK: replay only" note. Last run id kept in sessionStorage (`qs.lastRunId`, try/catch).
- Rejection log: stream rejections or stored rejections.csv (labelled REPLAYED/stored), category filter with counts, norm gate labelled "plaintext norm gate (not ZK)", not_in_quorum shown as round-level. Stored CSV has no category column, so `categorize()` in `reasons.ts` maps raw reasons client-side using the contract's table (a duplicate of backend reasons.py; replace if the backend adds a category to the stored rows).
- `/zk` (`components/zk/ZkView.tsx`): per-round status table and receipt cards, ReplayedBadge + API label on every result, verified true/false/unknown, sizes, prove_s, cycles, peak memory, hardware block, mtime note. No LiveBadge.
- `/consensus` (`components/consensus/ConsensusView.tsx`): run picker (session run or pasted id), parameters, rounds table, D-020 view-change note from API, certificate chain (round -> certificate -> model hash), per-round "Verify certificate (public keys only)" with per-vote results, public-keys-only statement, 501 and other errors shown.
- `/attacks` (`components/heatmap/AttackHeatmap.tsx` + css module): attack x defence grid from attack_matrix, sequentialColor with flipped ink, diverged cells use `.qs-diverged-fill` + DivergedMarker, each cell prints mean, std, n, diverged k of n, rejected, delta vs benign cell; FLAG text for "attack not stopped: 0 rejected" and "defence on, still diverged"; legend, hover/focus detail, table view. D-012 and replay-row notes are taken from /api/limitations (matched by text, markdown stripped).
- `npm run lint`, `npm run typecheck`, `npm run build` pass. No types.ts changes.

## Verified
- Backend imported on port 8011 (8000 was occupied by something else); checked the response shapes of attack_matrix, zk/rounds and limitations against my parsing.

## Unverified
- No browser rendering/visual check (light/dark, phone width) and no end-to-end run stream, consensus view or certificate verify against a live backend. Layout is written responsively but not looked at.
- Rejection-log stored view and receipts cards were not fetched live.
- The heatmap uses the sequential scale only (no diverging scale), so the unvalidated diverging arms are not relied on.

## For the lead
- Page `/` and port 8000: something non-QuantumShield answered 404 on 8000 during my check.
