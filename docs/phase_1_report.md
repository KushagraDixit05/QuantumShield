# Phase 1 Report — Fixed-point FL baseline and attack suite

Scope: Phase 0 (ZK statement freeze) and Phase 1. No signatures, ZK guest, or consensus have been started.

## Hardware / software
Intel i5-11260H (12 threads), 7.5 GB RAM, Linux 7.0.0, Python 3.11.17 (uv venv), numpy 2.4.6, scikit-learn 1.9.1. CPU only; no GPU used. The whole baseline grid takes ~25 s and negligible memory.

## What was built
| Path | Purpose |
|---|---|
| `docs/zk_statement.md` | Frozen relation: commitment opening, norm bound, K SGD steps on Merkle-committed sampled data; exact fixed-point semantics; explicit "not proven" list |
| `docs/decisions.md` | D-005..D-013: conflicts between brief and plan, design calls |
| `fl/fixedpoint.py` | int64 fixed point (scale 2^16), floor shifts, pre-multiplication overflow guards, exact `norm_sq` |
| `fl/merkle.py` | SHA-256 Merkle tree with domain separation and path verification (not yet wired into training) |
| `fl/data.py`, `fl/model.py` | sklearn digits (pixel `p << 12`), IID 5-way split, integer MLP 64→32→10 (2,410 params) |
| `fl/client.py` | SHA-256-based public sample-index rule; K integer SGD steps (one-hot MSE) → Δ |
| `fl/aggregate.py` | `fedavg`, `norm_filter_mean`, `coord_median`, `clip_mean` (all integer) |
| `attacks/poison.py` | `scaled`, `sign_flip`, `label_flip`, `replay` |
| `fl/simulate.py`, `experiments/run_baseline.py`, `configs/*.yaml` | One-command, seeded experiments |
| `tests/` | 34 tests (32 new) |

Parameters: 5 clients (1 malicious), 10 rounds, K=20 steps, batch 32, lr 0.3, B = 1.5963 (‖Δ‖ in real units). Training is integer-only; no floats in the forward/backward/update path (floats only for init sampling and reporting).

## Commands and real output
```
$ .venv/bin/python -m pytest -q
..................................                                       [100%]
34 passed in 15.82s

$ .venv/bin/python -m experiments.run_baseline --calibrate
calibration seed=100: benign ||Δ|| median=0.4450 p99=1.0642 max=1.0700 -> B=1.5963

$ make baseline          # == python -m experiments.run_baseline --config configs/baseline.yaml
... (see table) ...
done in 25.4s -> demo/results/baseline.csv, demo/results/baseline.md

$ make baseline; diff demo/results/baseline.csv <previous run>     # reproducibility
IDENTICAL

$ python -m fl.simulate --attack scaled --defence norm_filter --seed 1     # single run
```
Per-round curves for every run are in `demo/results/baseline.csv`.

## Baseline results
Final-round (round 10) test accuracy on 359 held-out samples, mean ± std (population std) over seeds {0,1,2,3,4}. Diverged runs (int64 range exceeded) are scored 0.0 (convention D-012).

| attack | FedAvg | norm filter (plain, B=1.5963) | coord. median | norm-check rejections malicious / benign |
|---|---|---|---|---|
| none (benign) | 0.9421 ± 0.0145 | 0.9421 ± 0.0145 | 0.9426 ± 0.0156 | 0/50 / 0/200 |
| scaled ×50 | 0.0000 ± 0.0000 (diverged 5/5) | 0.9376 ± 0.0165 | 0.9443 ± 0.0165 | 50/50 / 0/200 |
| sign-flip ×1 | 0.9075 ± 0.0175 | 0.9075 ± 0.0175 | 0.9253 ± 0.0154 | 0/50 / 0/200 |
| label-flip (y→y+1) | 0.9253 ± 0.0131 | 0.9253 ± 0.0131 | 0.9331 ± 0.0163 | 0/50 / 0/200 |
| replay (stale Δ) | 0.9265 ± 0.0189 | 0.9265 ± 0.0189 | 0.9348 ± 0.0182 | 0/50 / 0/200 |

Paired per-seed accuracy drop vs. benign, same defence (mean ± std over 5 seeds): FedAvg sign-flip 3.45 ± 1.55 pts, label-flip 1.67 ± 0.88, replay 1.56 ± 1.23 (worse in 5/5 seeds each); median sign-flip 1.73 ± 1.23, label-flip 0.95 ± 0.99 (4/5), replay 0.78 ± 0.99 (3/5).

Note the test set granularity is ~0.28 pts per sample; differences of 1–2 pts with 5 seeds are suggestive, not strong evidence.

## What each defence does and does not catch
- **Plain FedAvg:** catches nothing. One ×50 update destroys it (the model leaves int64 range in 5/5 seeds).
- **Norm filter (plain ‖Δ‖² ≤ B² comparison, not a proof):** catches the scaled attack (50/50) with no false rejections of benign updates (0/200). It does **not** catch sign-flip ×1, label-flip or replay: their norms are benign-sized, so the numbers are identical to FedAvg by construction. This is what the ZK norm clause would enforce in Phase 3; the ZK version adds binding to a commitment, not extra detection power for these attacks.
- **Label-flip** is in-norm and, because the client trains honestly on the data it committed to, would also pass the planned SGD-consistency clause. Not caught by the ZK relation (see `zk_statement.md` §5).
- **Sign-flip ×1** would be caught by the SGD-consistency clause (−Δ is not what SGD on the committed data produces) but not by the norm clause.
- **Replay** is invisible to the FL layer; it is meant to be stopped by round-bound, nonce-tracked signed envelopes and the proof's public inputs (Phase 2/3). Not tested here beyond showing the FL layer accepts it.
- **Coordinate median:** reduces the in-bound attack damage (1–2 pts) but needs plaintext Δ, offers no proof, and in this run costs nothing on benign data (0.9426 vs 0.9421). It was not tuned or tested against stronger adaptive attacks.

## Deviations from the plan and open issues
Deviations (details in `docs/decisions.md`): fixed-point integer baseline instead of PyTorch (D-008); one-hot MSE loss (D-009); four attacks instead of one (D-007); the statement includes SGD/Merkle clauses the approved plan deferred (D-006); init and lr tuned on seeds 100–104 (D-011); diverged-run convention (D-012). The brief's `00_README_Overview.md`/`Phase_N` files do not exist (D-005).

Open issues:
1. The SGD rule, floor shifts, SHA-256 index sampling and Merkle verification are only specified and tested in Python. Nothing has been run in the RISC Zero guest yet; the cost of proving K=20 steps × batch 32 is unmeasured and may force a smaller K/batch (cut ladder).
2. `fl/merkle.py` is tested but not yet used by the client/simulator; the label-flip attack does not yet re-commit poisoned data.
3. Hyperparameter tuning seeds (100–104) include the calibration seed 100; evaluation seeds 0–4 were not used for tuning. B was calibrated on a single seed; all 200 benign client-rounds on the evaluation seeds passed the bound, with a worst case not reported here.
4. Single dataset (digits, 1,797 samples), IID only, 10 rounds, 1 of 5 clients malicious; accuracy 94% is lower than MNIST-scale baselines and not comparable to them.
5. Tuning showed the benign norm distribution depends strongly on initialisation scale (round-0 norms up to 4.6 with He init). B must be recalibrated if the model, init or hyperparameters change.
6. No Phase 2/3 code, no signatures, no proofs: `norm_filter` is a plaintext check, and Δ is visible to the aggregator.
