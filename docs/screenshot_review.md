# Screenshot review (Agent S)

All five images are 1280 px wide light-theme captures (page background light, sidebar dark). Header shows badge "ZK: REPLAY ONLY", "backend up | queue 0" and a button "Light theme" (unclear whether it names the current or target theme). The dark sidebar ends at about 720 px in tall captures (capture artefact of a viewport-height sidebar, not judged a defect). Overheads and limitations were viewed in crops; text was legible.

## 1. docs/screenshots/overview.png (1280x1577)
Route: Overview. Light theme. Scenarios A/B/C chart (stored run, seed 0, 10 rounds) and "Summary across seeds" table.
Numbers checked against demo/results/scenarios.json and scenarios.csv (the page's named sources):
- Chart A/C converge near 0.95 at round 10; B peaks about 0.30 at round 1 then about 0.11, 0.09. json B = 0.3008, 0.1114, 0.0919, 0.1114, 0.0919, 0.1114 then 0.0 from index 7. Match. B line stops at index 6, shaded region and dashed line at 7, label "B DIVERGED". Match (0.0 not plotted).
- Table: none/off 0.9421, std 0.0145, rejected 0; none/on same; scaled/on 0.9376, 0.0165, 50; forged/on 0.9409, 0.0161, 50; replay off and on 0.9370, 0.0158, 45. All match scenarios.csv (recomputed with population std). Scaled/off and forged/off show "DIVERGED 5 of 5", "n/a (all diverged)", std "n/a". Match (5 diverged each).
- Std column header says "STD (POPULATION, N)", which resolves UI-G-C-1.
- 18 numbers checked, 0 mismatches.
Visual: no overlap, clipping, raw markdown or duplicated labels. D-012 callouts appear twice (under the chart and above the table) - intended. Legend text is readable. Colours are blue/orange/green lines; B is separable by marker and the shaded region.
Live vs replayed: no LIVE or REPLAYED badge on this page; header "ZK: REPLAY ONLY" only. Nothing ZK is shown, so no missing ZK label. Stored data is described as stored ("One stored run", "Source: ...").
Note (source quirk, not UI): replay/off shows 45 rejected, with defence off. It matches the CSV and limitation 10 explains it on the attack page.

## 2. docs/screenshots/attacks.png (1280x1509)
Route: Attack matrix. Light theme. 4x2 heatmap, scale legend, D-012 and replay callouts. Badge "COMPUTED BY BACKEND FROM STORED SCENARIOS.CSV".
Numbers (vs scenarios.csv, recomputed): none 94.2% +-1.4% rejected 0 (off) and same on with "+0.0 pts"; scaled/on 93.8% +-1.6% rejected 50, -0.4 pts (-0.45 exact); forged/on 94.1% +-1.6% rejected 50, -0.1; replay 93.7% +-1.6% rejected 45, -0.5 both modes; scaled/off and forged/off DIVERGED 5 of 5, rejected 0. Stds are population std (0.0145, 0.0165, 0.0161, 0.0158). 16 values checked, 0 mismatches. "+-1.6%" for 0.0165 is rounding. The heatmap does not say std is population (the Overview does); minor.
Diverged cells: drawn hatched with a "x DIVERGED 5 of 5" tag, not 0.0, and not on the scale (legend: "diverged (not on the scale)"). Each carries "FLAG ATTACK NOT STOPPED: 0 REJECTED". The D-012 explanation is in a callout below the matrix (not inside the cell, about 40 px below the legend), with Limitation 16 text. Colour: single-hue light-to-dark blue sequential scale (colour-blind safe), every cell prints its value, so colour is not the only carrier.
Visual: no clipping or overlap. Weak points: the hint box "Hover or focus a cell (arrow keys are not needed: tab between cells)" is oddly worded and in large grey type; the D-012 text partly repeats Limitation 16 in one callout.
Live vs replayed: no badges; the data badge states it is computed from stored CSV. No ZK result.

## 3. docs/screenshots/zk.png (1280x2816)
Route: ZK. Light theme. Title "Proof receipts (replayed)". "Replay only" explainer. Per-round table (6 rows), 4 receipt cards, hardware card.
Receipt ids on screen vs sha256[:12] of demo/results/zk/*.receipt (hashlib): r0_c0 22275a3c1aac, r0_c1 604fc87b9b47, r1_c0 a869f31b4406, r1_c1 ac01dd9fa6ee. All four match, in table, card badges and labels.
Other numbers vs demo/results/phase3_fl.csv and zk_bench.md: prove_s 379.7, 491.2 (csv 491.19), 494.9 (494.92), 610.4 (610.44); cycles 3,014,656 / 2,916,352; receipt size 3.06 / 3.02 MB (3,058,804 / 3,024,116 B); peak memory 2,367 / 2,368 MB; journal 146 B (file size 146); image id c66b4507...5360a10 matches zk_bench.md; hardware i5-11260H, 12 threads, 7.5 GiB, risc0-zkvm 3.0.6, CPU proving. Rounds 0 and 1 client 4: "NO RECEIPT", reason "guest_can_prove=False; bad_proof:missing_proof_hash", matches zk_consensus.csv attacker_reason. Generated dates 2026-10-08T19:18:54 UTC etc. equal receipt mtimes (ls shows Oct 9 00:48 local, +05:30). 30+ values checked, 0 mismatches. Not in any source file: verify_s per receipt (0.28, 0.21, 0.202, 0.209); these are consistent with bench range 0.22-0.24 but cannot be checked against a stored file.
Visual: no overlap or clipping. The label text is repeated three times per receipt (large badge, bold line, table row), heavy but not wrong. No raw markdown.
Live vs replayed: top badge "ZK: REPLAY ONLY"; section badges "REPLAYED" (stored zk_consensus.csv and phase3_fl.csv; stored receipt files, verified without proving). Every receipt row carries "replayed from receipt <id>, generated <date> (file mtime), on 11th Gen Intel(R) Core(TM) i5-11260H @ 2.60GHz, 12 threads, 7.5 GiB". The two NO RECEIPT rows say "replayed from stored results (no receipt file for this update)", so no result lacks the label. "Verified" statuses could be mistaken for a live check, but the badges and the "Replay only" box say otherwise. Nothing replayed is shown as live.

## 4. docs/screenshots/overheads.png (1280x4311; viewed in three crops)
Route: Overheads. Light theme. Sig size and time charts, envelope table, throughput chart, ZK stat cards and runs, latency table, hardware, benchmark summary.
Numbers vs sig_bench.csv, sig_bench_overhead.csv, sig_bench_throughput.csv, zk_bench.csv, scenarios.csv, overheads.md:
- Envelope table: 94/232/91; 2,454/2,592/2,451; 3,343/3,481/3,340; 688/826/689; 7,896/8,034/7,893; hybrid 3,436/3,574/3,430. All match.
- Latency table: 4.84, 6.88, 4.8, 7, 4.76, 6.72, 4.38, 6.38 ms; env bytes 232 / 3,574; n diverged 0,0,5,0,5,0,0,0. All match scenarios.csv.
- ZK cards: 393.4 s to 402 s, 0.222 to 0.238 s, 3.06 MB; per run 402 / 393.39, 3,014,656 cycles, po2 18. Match zk_bench.csv. Peak memory 2,365 / 2,367 MB (csv 2421732/2423628 kB) ok; zk_bench.md says 2364/2366.
- Charts (read by eye on log axes): signature bytes Ed25519 about 64, ML-DSA-44 about 2,420, SLH about 7,856 and Falcon sig about 656 consistent; time chart Falcon keygen about 5 ms, SLH sign about 450 ms consistent; throughput lines about 21k (ML-DSA-44), 17k (ML-DSA-65, Falcon), 8k (Ed25519), 7k (hybrid), 2.3k (SLH), consistent with csv.
- Hardware block and "Limitation 18" 20% chip match zk_bench.md and limitations.md. 40+ values checked; 0 data mismatches (one unit issue below).
Defects: see UI-G-S-2 (envelope table clipped on right), UI-G-S-3 (benchmark summary pre block cut off at the markdown table header, raw pipes shown), UI-G-S-4 (throughput x axis 50/100/500 evenly spaced), UI-G-S-5 (ZK section lacks the per-result receipt label), UI-G-S-6 ("2.31 GB to 2.31 GB" vs 2,365 MB).
Live vs replayed: intro says "All figures are stored benchmark results"; ZK section has a REPLAYED badge. Signature/latency charts have no badge but are described as stored. ZK numbers here do not state receipt id, generation date or hardware beside them (hardware is in a card below), so this section does not meet the "replayed from receipt ..." labelling.

## 5. docs/screenshots/limitations.png (1280x2296; two crops)
Route: Limitations. Light theme. Numbered 1-19 in five sections (Privacy, ZK relation, Signatures, Consensus and network, Measurement). Source caption: docs/limitations.md.
Compared with docs/limitations.md: all 19 items present and numbered 1-19; numbers K=4 batch 8, K=20 batch 32, 4.5 h, 0.76 vs 0.94, 4 real proofs, 3.45 +/- 1.55, 2,410 parameters, 359 samples, 0.28 points, seed 100 x 1.5, 20%, 2.4 GB, 3 MB all match. 15+ numbers checked, 0 mismatches.
Defect: UI-G-S-1, literal backticks around file names, reasons and formulas (e.g. `demo/results/zk_consensus.csv`, `make demo`, `||Delta||^2 <= B^2` drawn as "| |Delta| |^2"). Bold markers are rendered correctly. No ".." artefacts, no duplicated labels. Item 16 repeats D-012 consistently with the attack page.
Live vs replayed: no badges besides the header; no ZK result shown.

## Summary

| page | numbers checked | mismatches | defects | severity |
|---|---|---|---|---|
| overview | 18 | 0 | none visual | none |
| attacks | 16 | 0 | awkward hint wording; heatmap does not say std is population | cosmetic |
| zk | 30+ (4 receipt ids by hashlib, all match) | 0 | repetitive label text; verify_s per receipt not in any stored file | cosmetic |
| overheads | 40+ | 0 (GB vs MB unit, 1 MB source difference) | UI-G-S-2, S-3, S-4, S-5, S-6 | S-3 and S-5 medium, rest low |
| limitations | 15+ | 0 | UI-G-S-1 raw backticks | low |

Live/replayed: no replayed number is presented as live; the one labelling gap is the Overheads ZK section (UI-G-S-5). Diverged cells are correct (hatched, tagged, not 0.0, D-012 callout below the matrix, colour-blind-safe sequential blue, text in every cell).
