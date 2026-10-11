# Phase 5 report: Demo and proof-of-work package (MVP plan numbering)

Scope follows `plan/MVP_Phase_5_Demo_and_Proof_of_Work.md` (D-020). The brief's E1-E7 evaluation (non-IID, ablations, 100k-parameter ZK scaling, E3 algorithm comparison at scale, E5 consensus scaling) is **not done**; see `docs/deferred.md`.

## What was built
| item | path | by |
|---|---|---|
| Scenario driver, attack matrix, real-receipt consensus stage | `demo/run_demo.py`, `configs/demo.yaml` | lead |
| `make demo` / `make results` (+ `.PHONY`; the `demo/` directory made make skip the target before) | `Makefile` | lead |
| Accuracy-vs-round and attack-by-defence figures (5 tests) | `demo/plot.py`, `tests/test_demo_plot.py`, `demo/results/{accuracy,attack_matrix}.png` | Agent H |
| Overhead table with no pending cells (3 tests) | `demo/overheads.py`, `tests/test_overheads.py`, `demo/results/overheads.md` | Agent I |
| README, limitations, demo script, results write-up, deferred list | `README.md`, `docs/{limitations,demo_script,results_writeup,deferred}.md` | Agent J |
Status files: `docs/status/p5-{H,I,J}.md`. No agent ran the prover.

## Commands run and output
```
$ make demo      # run_demo --all, demo.plot, demo.overheads; files were deleted first and regenerated; about 21 s wall
$ .venv/bin/python -m pytest -q --ignore=tests/zk   -> 148 passed in 37.40s
$ .venv/bin/python -m pytest -q tests/zk            -> 116 passed in 14.62s  (cached Phase 3 receipt, no proving)
```
Generated: `scenarios.csv`, `scenarios.json`, `scenarios_summary.md`, `rejections.csv`, `zk_consensus.csv`, `accuracy.png`, `attack_matrix.png`, `overheads.md` in `demo/results/`. No number in this report comes from a dev-mode proof; the only proofs are the Phase 3 real receipts.

## Main results (seeds 0-4, K=20, batch 32, 10 rounds, 359 test samples, so 1-2 point gaps are suggestive only)
| attack | defence off (Ed25519 + FedAvg) | defence on (hybrid sig + norm gate) |
|---|---|---|
| none | 0.9421 +/- 0.0145 | 0.9421 +/- 0.0145 |
| scaled x50 | 0.0000 (diverged in 5/5; D-012 convention) | 0.9376 +/- 0.0165 |
| forged (stolen Ed25519 key) | 0.0000 (diverged in 5/5) | 0.9409 +/- 0.0161 |
| replay | 0.9370 +/- 0.0158 | 0.9370 +/- 0.0158 |
Rejections (`rejections.csv`): 50 `norm_bound_exceeded` (scaled/on), 50 `bad_signature` (forged/on), 40 `wrong_round` + 5 `stale_key` per mode (replay).

## Overheads (`demo/results/overheads.md`; Intel i5-11260H, 12 threads, 7.5 GiB, Linux 7.0.0-34, liboqs 0.16.0)
| metric | with QuantumShield | without |
|---|---|---|
| signature bytes / update | ML-DSA-65 3343, hybrid 3436 | Ed25519 94 |
| sign / verify ms (median, hybrid) | 0.144 / 0.129 | 0.060 / 0.098 |
| proof size (K=4, batch 8, composite) | 3,058,804 B | none |
| prove time | 397.7 s median (380-610 s in FL runs; ~1.6x variability) | none |
| verify time per proof | 230 ms | none |
| round latency (simulated, compute only) | 7.8 ms; 1615 ms with 8 real receipt verifications | 5.4 ms |
| envelope bytes / update | 3574 | 232 |
| envelope + delta + receipt | 3,081,658 | 19,512 |

## Exit criteria
- One command regenerates figure and tables: yes (`make demo`, ~21 s because only existing receipts are verified; nothing is re-proved).
- Benign within ~2 pts and poisoned-with-defence near baseline: yes (0.9376 vs 0.9421 mean over 5 seeds).
- Limitations explicit: `docs/limitations.md`.
- Screen recording: **not made** (the assistant cannot record); `docs/demo_script.md` is the script to record.

## Deviations, decisions, open issues
- The accuracy evidence uses a plaintext norm gate, not ZK, for ~50 updates per run; the ZK evidence is 4 real proofs at K=4 (2 rounds, 2 clients) from Phase 3. Different configs; the write-up says so.
- Replay shows no defence advantage: signatures reject it in both modes.
- Label-flip and in-bound sign-flip are not part of this demo and are not stopped by the norm check (Phase 1 report).
- `docs/results_writeup.md` claim 6 was corrected by the lead (columns come from `phase3_fl.csv`, not `zk_consensus.csv`); timing values were synced to the final run.
- Timings vary run to run; `scenarios.csv` latency and `overheads.md` change slightly on every `make demo`.
- Agent J's README setup prerequisites were not executed on a clean checkout.
