# QuantumShield-FL

MVP of a decentralized federated-learning (FL) pipeline in which every model update carries a post-quantum signature and a zero-knowledge proof, and each round is finalized by a 2f+1 PQ-signed vote. Scope is fixed by `plan/00_MVP_Overview.md`; design decisions are in `docs/decisions.md`.

## What the MVP claims

In a small decentralized FL network (4 simulated aggregator nodes, f=1), every model update carries an ML-DSA-65 signature (hybrid with Ed25519) and a RISC Zero proof that the update is committed, norm-bounded, and (at reduced size) the result of SGD steps on Merkle-committed data. Aggregators accept an update only if both verify, and finalize each round by a 2f+1 PQ-signed vote. A poisoning client whose update violates the norm bound is rejected, and a forged classical signature is rejected, while benign accuracy is unchanged (0.9421 with and without the defence, 5 seeds; `demo/results/scenarios_summary.md`).

This is evidence from one machine, a small model and a simulated network. It is not a security proof. Read `docs/limitations.md` before relying on any statement above.

## Run

Using the web UI: see `USER_GUIDE.md` (`make ui-install`, then `make ui`).

```
make setup   # venv + requirements (liboqs is built from source by liboqs-python; needs a C toolchain)
make test    # pytest (tests/zk needs the built qs-zk binary: `make zk-build`, requires the RISC Zero toolchain)
make demo    # python -m demo.run_demo --all, then demo.plot, then demo.overheads
```

`make demo` regenerates the scenario tables, the rejection log, the ZK + consensus check, the accuracy figure and the overhead table. It does NOT run the prover: the ZK stage verifies the four stored receipts in `demo/results/zk/`. Producing new receipts is `make phase3` (about 6 minutes and 2.4 GB RAM per proof). Single scenario: `python -m demo.run_demo --stage scenarios --attack scaled --defence on --seeds 0`. Walkthrough: `docs/demo_script.md`.

## Layout

| Path | Contents |
|---|---|
| `fl/` | Integer fixed-point MLP (64-32-10, 2,410 params), IID split, local SGD, aggregation, Merkle tree, Python reference of the ZK relation |
| `attacks/` | scaled, sign-flip, label-flip, replay (data level); forged signature, proof swap (envelope level) |
| `pq/` | ML-DSA-65 / Falcon-512 / SLH-DSA / Ed25519 / hybrid signing, envelope v1/v2, verifier, ZK policy, benchmarks, forgery demo |
| `zk/` | RISC Zero guest, `qs-zk` host CLI, Python bridge and test vectors |
| `consensus/` | 4 asyncio nodes, signed votes, 2f+1 finalization, fault modes |
| `demo/` | `run_demo.py`, `plot.py`, `overheads.py`, `results/` |
| `docs/` | decisions, per-phase reports, interfaces, limitations, demo script, write-up, deferred list |
| `plan/` | The approved MVP plan |

## Results

| What | Where |
|---|---|
| Final accuracy per attack and defence setting, 5 seeds | `demo/results/scenarios_summary.md`, `scenarios.csv` |
| Accuracy vs round (A benign / B poisoned, no defence / C poisoned, defence) | `demo/results/accuracy.png` |
| Attack outcome matrix | `demo/results/attack_matrix.png` |
| Rejections with reasons | `demo/results/rejections.csv` |
| Real proofs through the 4-node vote | `demo/results/zk_consensus.csv` |
| Signature forgery demonstration | `demo/results/forgery.md` |
| Overheads (sizes, times, latency) | `demo/results/overheads.md` |
| One-page write-up | `docs/results_writeup.md` |

## Limitations (summary; full list in `docs/limitations.md`)

- Not private: the update Delta is sent in the clear to aggregators. The proof does not hide it.
- The ZK relation (commitment + norm + SGD recompute on Merkle-committed data) is proved only at K=4 steps, batch 8, not the K=20, batch 32 used for accuracy runs. Only 4 real proofs exist (2 rounds x clients 0 and 1).
- The accuracy scenarios (50 client updates per run) use a plaintext norm gate in place of ZK, so ZK evidence and accuracy evidence come from different configurations.
- In-bound attacks (label-flip, small sign-flip, slow poisoning) are not stopped; the committed dataset is not attested.
- The network is simulated (asyncio, fixed leader, no view change, n=4, f=1 only). Small model, 359-sample test set: differences of 1-2 points are suggestive only.
- Deferred work is listed in `docs/deferred.md`.
