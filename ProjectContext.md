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



# QuantumShield-FL User Guide

This guide shows how to set up the project, start the web UI, and read what it shows. For the design and the
claims, read `README.md`. For what the project does **not** prove, read `docs/limitations.md` first.

## 1. What you are looking at

QuantumShield-FL is a small decentralized federated-learning (FL) pipeline. Every model update carries a
post-quantum signature (ML-DSA-65, hybrid with Ed25519) and, in the ZK stage, a RISC Zero proof. Four simulated
aggregator nodes finalize each round by a 2f+1 signed vote (n=4, f=1).

The web UI lets you run attack scenarios, look at the stored zero-knowledge receipts, check consensus votes, and
compare overheads. It is evidence from one machine, a small model (2,410 parameters) and a simulated network. It is
not a security proof.

## 2. Requirements

- Linux, with a C toolchain (liboqs is built from source by `liboqs-python`)
- Python 3.11, in the project virtualenv `.venv`. Always use `.venv/bin/python`: the signature library (`oqs`) is only installed there.
- Node 24 and **npm** (the only package manager used; do not use pnpm or yarn)
- About 7.5 GB RAM. The UI never proves anything, but a real proof (`make phase3`) needs about 2.4 GB for about 6 minutes.
- Optional, only for new ZK receipts and `tests/zk`: the RISC Zero toolchain (`make zk-build`)

## 3. One-time setup

From the project root:

```
make setup        # creates .venv and installs requirements.txt
make ui-install   # npm install in frontend/ and tests/e2e/
```

## 4. Start and stop the UI

```
make ui
```

This rebuilds the frontend, then starts both servers:

| Part | Address |
|---|---|
| UI | http://127.0.0.1:3000 |
| Backend API | http://127.0.0.1:8000 (interactive API docs at `/docs`) |

- The backend needs a few seconds to import its libraries after the UI is up. If a page says **backend unreachable**, wait a moment and reload.
- Press **Ctrl-C** in that terminal to stop both servers.
- Ports 8000 and 3000 must be free. The backend only accepts browser requests from `localhost`/`127.0.0.1` on ports 3000 and 3001.
- To run only the backend: `make api`.
- Quick check: `curl http://127.0.0.1:8000/api/health` should return `{"ok":true,"live_zk_enabled":false,...}`.

`make ui` always rebuilds because `make ui-test` leaves a build that points at a different backend port (8011), and
serving that build would break every page.

The top bar shows the backend status and a permanent **ZK: replay only** chip. There is a light/dark theme toggle.

## 5. Using the screens

The left navigation has seven pages.

### Overview
Accuracy curves for the three standard scenarios (seed 0) and a summary table over all stored seeds. Read it to see
the headline result: with the defence on, benign accuracy is unchanged; with no defence, the poisoned run diverges.

### Run (scenario runner)
Run a scenario live and watch it round by round.

1. Pick **Preset A / B / C**, or **Custom attack and defence**:
   - **A**: benign, no attack
   - **B**: poisoned client, plain FedAvg (no defence)
   - **C**: poisoned client, QuantumShield on
2. For a custom run, choose the attack (`none`, `scaled`, `forged`, `replay`), the defence (`on` or `off`) and the aggregator (`fedavg`, `norm_filter`, `median`, `clip`). The **Attack enabled** box turns the attack on or off.
3. Tick the seeds (0 to 4), set the number of rounds (1 to 50; the stored results use 10).
4. Press **Run**. The output is marked **LIVE**: it is computed now by the backend.

You will see accuracy per round (one line per seed), accepted and rejected update counts per round, and a per-seed
final result. Runs go through a queue and execute one at a time. There is no cancel: **Stop watching** only closes
the stream, and the backend finishes the run. Each run shows a run id; keep it for the Consensus page.

**Rejection log** (below the runner). Every rejected update with its round, client, category and the exact reason
string. Categories are bad signature, wrong round, norm bound exceeded, failed proof, replay, not in quorum and
other. You can switch between this session's rejections and the stored `demo/results/rejections.csv`. A rejection for
`norm_bound_exceeded` is labelled **plaintext norm gate (not ZK)**: the live scenarios check the norm bound directly
and do not generate a proof.

### ZK
Replay only. Live proving takes about 6 minutes and 2.4 GB per proof, so this page shows the four stored receipts
and what the verifier says about them. Nothing is proved when you open it.

- Every result carries a **REPLAYED** badge and a label of the form: *replayed from receipt `<id>`, generated `<date>`, on `<hardware>`*.
- The receipt id is the first 12 hex characters of the receipt file's SHA-256. "Generated" is the file's modification time. The receipt files carry no metadata of their own.
- The hardware comes from `demo/results/zk_bench.md` and `docs/zk_cost.md`.
- Rows marked **NO RECEIPT** are updates the prover could not prove (for example the attacker's scaled update).

### Consensus
1. Run a scenario on the Run page. Its run id is remembered in your browser tab and loaded here automatically, or paste a run id and press **Load**.
2. The table lists each round with the leader (always node 0), votes, quorum (3 of 4), whether it finalized, equivocators and bad votes.
3. Press **Verify certificate (public keys only)** on a round. The backend checks that round's signed votes using public keys only; no secret key is used.

Limits to know: this consensus has a fixed leader and no view changes (deferred, decision D-020). A "certificate" here
is the round's set of signed votes, so the check verifies those votes and the 2f+1 quorum; it is not a chained
certificate.

### Overheads
Signature and public-key sizes and times, per-update envelope overhead, verification throughput, ZK prove and verify
time, receipt size and peak memory, round latency and bandwidth, and the hardware the numbers were measured on.
Timings come from a single machine and vary roughly 20% between runs.

### Attack matrix
A heatmap of attack against defence with the actual outcomes, including failures and misses. Each cell prints its
values (mean final accuracy, spread, number of seeds, how many diverged, how many updates were rejected), so colour
is never the only signal. Hover or focus a cell for details; a table view is available.

### Limitations
The limitations list from `docs/limitations.md`, grouped by its headings. Read it before relying on any number.

## 6. Reading the results honestly

- **Sources.** Every chart and table shows the file it came from (`Source: ...`). Stored results are in `demo/results/`.
- **DIVERGED.** In a poisoned run without the defence, the model leaves the int64 fixed-point range and the run stops. The stored files record such rounds as accuracy `0.0`. That is a convention (decision D-012), not a measured accuracy. The UI shows these as **DIVERGED** and never plots them as 0. A run stops at its divergence round, so later rounds do not exist.
- **Standard deviation** is the population standard deviation (n), as in `demo/results/scenarios_summary.md`.
- **Replay attack.** Replayed updates are rejected in both modes, so that row does not show an advantage for the defence.
- **LIVE vs REPLAYED.** LIVE means the backend computed it just now (the Run page). REPLAYED means it is read from a stored file or receipt. ZK results are always REPLAYED.

## 7. Working from the command line

```
make demo        # regenerate demo/results: scenarios, rejection log, ZK check, figures, overhead table (no prover)
make test        # full pytest suite (tests/zk needs the built qs-zk binary: make zk-build)
make ui-test     # backend tests, schema check, frontend lint/typecheck/build, browser tests
make ui-gen      # regenerate the OpenAPI types after changing the backend schema
make phase3      # produce new real ZK receipts: about 6 minutes and 2.4 GB per proof
```

Run one scenario without the UI:

```
.venv/bin/python -m demo.run_demo --stage scenarios --attack scaled --defence on --seeds 0
```

Notes:
- `make ui-test` uses its own ports (8011 and 3001), so it can run while the UI is open, but do not run it together with other heavy jobs on a 7.5 GB machine. Run `make ui` again afterwards (it rebuilds).
- Only one prover may run at a time. Proving takes the lock file `.zk_prove.lock`, and the UI never proves.

## 8. Where things are

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (runs, queue, results, receipts, certificates) |
| `frontend/` | Next.js UI (npm, Node 24) |
| `demo/results/` | Stored results and receipts that the UI displays |
| `fl/`, `pq/`, `zk/`, `consensus/`, `attacks/` | The FL, signature, ZK, consensus and attack code. The UI only calls it. |
| `tests/backend`, `tests/hardening`, `tests/e2e` | API tests, certificate tests, browser tests |
| `docs/api_contract.md` | Every API endpoint and the event stream format |
| `docs/limitations.md`, `docs/decisions.md` | What is not proved; design decisions (D-012 divergence, D-020 deferred consensus features) |
| `docs/ui_report.md`, `docs/ui_issues.md` | UI test results and known issues |

## 9. Troubleshooting

| Symptom | What to do |
|---|---|
| Pages show **backend unreachable** | The backend is still starting (wait a few seconds), or it is not running (`make api`). If the UI was built against another API address, run `make ui-build`. |
| `port already in use` | Run `ss -ltnp` and look for ports 8000 and 3000, then stop that process (or the old `make ui`). |
| Out of memory | Use `make ui` (production build), not `npm run dev`. Do not run `make ui-test`, a proof and the UI together. |
| Run says it is queued | Only one run executes at a time; yours starts when the current one finishes. |
| A request with `live_zk: true` returns 422 | By design: live proving is disabled in the UI backend. |
| Consensus page is empty | Run a scenario first, then open Consensus, or paste its run id. |

Known open UI issues are listed in `docs/ui_issues.md` (for example, the Run page shows per-seed results but not a
mean ± std line over the chosen seeds).


# QuantumShield-FL — MVP Overview (Proof of Work)

## 1. Claim the MVP must prove
> In a small decentralized FL network, every model update carries a **post-quantum signature** and a **zero-knowledge proof** that it satisfies a checkable integrity relation (committed + norm-bounded). Aggregator nodes accept an update only if both verify, and finalize each round by a **2f+1 PQ-signed vote** — so a poisoning client is rejected while benign accuracy is preserved.

If the demo shows this on one machine with real numbers, the MVP is done. Everything else is deferred.

## 2. Scope
| In MVP | Deferred (see `../plan/`) |
|---|---|
| FedAvg sim, tiny MLP, MNIST/sklearn-digits, IID split | Non-IID, CIFAR-10, larger models |
| ML-DSA-65 signatures on updates and votes | Falcon / SLH-DSA comparison, key rotation |
| ZK relation: commitment opens to Δ AND ‖Δ‖² ≤ B² | SGD-step recomputation, data-Merkle authentication |
| 4 simulated aggregator nodes (asyncio), f=1, 2f+1 votes | Real network, view change, full HotStuff/PBFT |
| One poisoning attack (scaled/noisy update) + forged signature + replay | Full attack suite, adaptive attackers |
| Overhead table (sig/proof size, prove/verify time, round latency) | Scaling plots to 100k params, ablations |
| Honest note: Δ reaches aggregators (ZK hides data, not Δ) | Secure aggregation / DP |

## 3. Architecture
```
 Client i                                      Aggregator node j (of 4, f=1)
 ┌───────────────────────────┐   envelope     ┌────────────────────────────┐
 │ train locally -> Δ_i       │  (round,id,    │ 1 verify ML-DSA signature   │
 │ C_i = H(Δ_i || nonce)      │   C_i, π_i,    │ 2 verify ZK proof π_i       │
 │ π_i = prove(C_i, B; Δ_i)   │──  σ_i)  ────▶ │ 3 robust-avg valid updates  │
 │ σ_i = MLDSA.sign(envelope) │                │ 4 sign vote on H(W_{t+1})   │
 └───────────────────────────┘                │ 5 finalize at 2f+1 votes    │
                                               └────────────────────────────┘
```

## 4. Tech stack
- Python 3.11, numpy / PyTorch (CPU), pytest, matplotlib
- PQ: `liboqs-python` (fallback `dilithium-py`, pure Python)
- ZK: `zk/` behind `prove(witness, public) -> bytes`, `verify(proof, public) -> bool`. Backends: `mock` (day 1, clearly labelled) → `risc0` zkVM (hash-based STARK, PQ-plausible). No Groth16 (pairings are not PQ).
- Consensus: in-process `asyncio` simulation

## 5. Repo layout
```
quantumshield-fl/
├── fl/          # model, data split, local train, aggregation
├── pq/          # ML-DSA wrapper, envelope, benchmarks
├── zk/          # prove/verify API, mock + risc0 backends, guest code
├── consensus/   # nodes, votes, round finalization
├── attacks/     # scaled update, forged sig, replay
├── demo/        # run_demo.py, plots, results/
├── tests/
└── README.md
```

## 6. Timeline (~3 weeks)
| Phase | File | Time | Shrinks full-plan phase |
|---|---|---|---|
| 0 | MVP_Phase_0_Setup_and_Scope_Freeze | 1–2 d | 1 |
| 1 | MVP_Phase_1_FL_Baseline_and_Attack | 3–4 d | 2 |
| 2 | MVP_Phase_2_PQ_Signatures | 2–3 d | 3 |
| 3 | MVP_Phase_3_ZK_Update_Verification | 5–7 d | 4 |
| 4 | MVP_Phase_4_Consensus_Lite_and_Integration | 3–4 d | 5–6 |
| 5 | MVP_Phase_5_Demo_and_Proof_of_Work | 2–3 d | 7–8 |

Phases 2 and 3 are independent after Phase 1 and can overlap; Phase 3 starts with the mock backend so Phase 4 is never blocked.

## 7. MVP Definition of Done
- [ ] P1: baseline accuracy recorded; poisoning attack measurably degrades it
- [ ] P2: every update and vote is ML-DSA signed and verified before use; forged/tampered messages rejected
- [ ] P3: every accepted update has a verifying proof (real backend); scaled update and tampered inputs fail
- [ ] P4: round finalizes with 2f+1 PQ votes; survives 1 silent/faulty node
- [ ] P5: three-scenario demo + accuracy plot + overhead table; one-command repro; benign accuracy within ~2 pts of baseline


# MVP Risks & Cut Ladder

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| liboqs build/install fails | Medium | Fallback to `dilithium-py` (pure Python, slower, same ML-DSA); cap at 2 hours |
| RISC Zero toolchain/proving too slow or won't install | Medium-High | Mock backend from day 1; shrink model; norm-on-subset; real numbers on toy size |
| Proof generation exceeds demo time budget | Medium | Precompute proofs per round, small model, fewer rounds/clients |
| Fixed-point overflow or mismatch between client and guest | Medium | Single shared quantization module, property tests |
| Scope creep ("just add SGD check") | High | Everything outside `00_MVP_Overview.md` §2 "In MVP" goes to Deferred |

## Cut ladder (cut from the bottom up if time runs short)
1. Keep: PQ sign/verify, ZK norm+commitment (any backend, labelled honestly), 4-node vote, 3-scenario demo
2. Cut first: ECDSA comparison table, equivocation fault mode, memory benchmarks
3. Then: real ZK backend → mock backend with real-backend numbers on a toy vector
4. Then: asyncio nodes → sequential in-process function calls

## What not to claim
- Not "full privacy": Δ is visible to aggregators in the MVP
- Not "proof of honest training": only commitment + norm bound is proven
- Not "quantum-secure ZK" if the mock backend is used
- Not a production consensus protocol: simulated, no view change


# MVP Phase 0 — Setup & Scope Freeze (1–2 days)

## Goal
A working environment and a frozen, written MVP scope so later phases don't drift.

## Tasks
- [ ] Create repo `quantumshield-fl/` with the layout in `00_MVP_Overview.md`; `git init`; venv; `requirements.txt`
- [ ] Install and smoke-test `liboqs-python` (sign/verify one message with ML-DSA-65). If the build fails within 2 hours, switch to `dilithium-py` and note it
- [ ] Install ZK toolchain (Rust + RISC Zero `rzup`) and run its hello-world prove/verify. If it fails within half a day, plan on `mock` backend + attempt later (see Risks)
- [ ] Freeze parameters in `config.py`: n=4 aggregators, f=1, 5 clients (1 malicious), rounds=10, model 784→32→10 (or sklearn digits 64→32→10), fixed-point scale 2^16, norm bound B
- [ ] Write `docs/mvp_statement.md`: public inputs (round, C_i, B), private witness (Δ_i, nonce), checks (opening, norm bound); threat model in 5 bullets (poisoning client, forged signature, replay, one faulty aggregator, quantum adversary on classical signatures)
- [ ] Define the signed envelope fields: version, round, client_id, C_i, proof hash, nonce

## Files created
`config.py`, `requirements.txt`, `docs/mvp_statement.md`, empty module folders, `tests/test_smoke.py`

## Exit criteria
- [ ] ML-DSA sign/verify smoke test passes
- [ ] ZK toolchain hello-world runs, or the fallback decision is written down
- [ ] `docs/mvp_statement.md` committed and frozen

## Deferred
CI, Docker, experiment tracking.


# MVP Phase 1 — FL Baseline & Attack (3–4 days)

## Goal
A minimal federated-learning loop plus one attack that visibly breaks it. This is the "problem" half of the demo.

## Tasks
- [ ] `fl/data.py`: load MNIST (or sklearn digits for zero download), IID-split across 5 clients, shared test set
- [ ] `fl/model.py`: tiny MLP, flatten/unflatten parameters to a single vector
- [ ] `fl/client.py`: `local_train(W_t) -> Δ_i` (1–2 epochs SGD)
- [ ] `fl/aggregate.py`: FedAvg; coordinate-wise median or norm-clipped mean as the "robust" option used later
- [ ] `fl/simulate.py`: run R rounds, log test accuracy per round to CSV
- [ ] `attacks/poison.py`: malicious client sends `Δ * s` (scale, e.g. s=50) or large Gaussian noise
- [ ] Record: clean-baseline accuracy, accuracy under attack with plain FedAvg

## Tests
- Parameter flatten/unflatten round-trips
- Clean FedAvg reaches expected accuracy (≥ ~90% on MNIST MLP, or the digits equivalent)
- Attack run is clearly worse than clean run

## Exit criteria
- [ ] `python -m fl.simulate --attack none|scaled` produces two accuracy curves
- [ ] Baseline numbers written to `demo/results/baseline.csv`
- [ ] Norm bound B chosen from benign update norms (e.g. 99th percentile × margin) and saved to config

## Deferred
Non-IID splits, other datasets, other attacks.


# MVP Phase 2 — Post-Quantum Signatures (2–3 days)

## Goal
Every update and every consensus vote is signed with ML-DSA and verified before use. Can run in parallel with Phase 3.

## Tasks
- [ ] `pq/sig.py`: `keygen()`, `sign(sk, msg)`, `verify(pk, msg, sig)` over ML-DSA-65 (liboqs; fallback `dilithium-py`)
- [ ] `pq/envelope.py`: canonical serialization of the envelope (version, round, client_id, C_i, proof hash, nonce); `sign_envelope`, `verify_envelope`
- [ ] Simple key registry: client and aggregator public keys known to all nodes (static, generated at startup)
- [ ] Replay protection: reject an envelope whose (client_id, round, nonce) was already seen or whose round is not current
- [ ] `pq/bench.py`: ML-DSA-65 vs ECDSA-P256 (via `cryptography`): key size, signature size, sign time, verify time → `demo/results/sig_bench.csv`

## Tests (`tests/test_pq.py`)
- Valid envelope verifies
- Flip one byte of payload → fails; wrong key → fails; forged signature → fails
- Replayed envelope → rejected; wrong round → rejected

## Exit criteria
- [ ] All tests pass
- [ ] Benchmark table produced
- [ ] `verify_envelope` is the only entry point aggregators use (no unsigned path)

## Deferred
Falcon / SLH-DSA, hybrid classical+PQ, key rotation, certificate chain.



# MVP Phase 3 — Zero-Knowledge Update Verification (5–7 days)

## Goal
A client proves, without revealing Δ_i, that (1) its commitment C_i opens to Δ_i and (2) ‖Δ_i‖² ≤ B². This alone stops scaled/noisy poisoning. Hardest phase — build in increments, each runnable.

## Relation (from `docs/mvp_statement.md`)
- Public: round t, commitment C_i, bound B
- Private: Δ_i (fixed-point ints), nonce
- Checks: `H(Δ_i || nonce) == C_i` and `Σ Δ_i[k]² ≤ B²` (integer arithmetic, no overflow)

## Increment ladder
1. **API + mock backend (day 1).** `zk/api.py`: `prove(witness, public) -> bytes`, `verify(proof, public) -> bool`. The mock checks the relation in the clear and emits a tagged blob. **Must be labelled "MOCK — not zero-knowledge" in logs and the README.** This unblocks Phase 4 immediately.
2. **Fixed-point quantization.** `zk/fixedpoint.py`: float Δ → int vector, scale 2^16, clamp; commitment function shared by client and guest.
3. **Real backend (days 2–5).** RISC Zero zkVM: Rust guest program implementing the relation, host CLI called from Python via subprocess (`prove`/`verify` JSON in, bytes out). Hash-based STARK core, so PQ-plausible. Use a small model (≈25k params) to keep proving tractable.
4. **Bind proof to the signature.** Signed envelope includes H(proof) and public inputs, so a proof can't be swapped or reused across rounds.
5. **Negative tests and benchmarks (days 5–7).**

## Tests (`tests/test_zk.py`)
- Honest update → verifies
- Scaled update (norm > B) → proof generation fails or verification fails
- Wrong commitment, wrong round, tampered public input, tampered proof bytes → verification fails
- Proof and public inputs contain no raw Δ values (assert Δ bytes absent)

## Benchmarks → `demo/results/zk_bench.csv`
Prover time, verifier time, proof size, peak memory for the demo model size.

## Fallbacks (in order)
1. Shrink hidden layer / parameter count
2. Prove norm bound over a fixed subset of coordinates plus full commitment (document the weaker statement)
3. Keep mock backend for the demo and state clearly it is a stand-in; report real-backend numbers on a toy size

## Exit criteria
- [ ] `prove`/`verify` work end to end on the real backend (or fallback 3 documented)
- [ ] All negative tests fail as expected
- [ ] Proof bound into the PQ envelope
- [ ] Benchmark row recorded

## Deferred
SGD-step recomputation, Merkle authentication of data samples, hand-written AIR (Winterfell/Plonky3), scaling plots, Groth16 comparison.


# MVP Phase 4 — Consensus-Lite & Integration (3–4 days)

## Goal
Wire FL + PQ signatures + ZK proofs into one verifiable round protocol across 4 simulated aggregator nodes tolerating f=1 faulty node.

## Round protocol
1. Leader broadcasts current model W_t and round number
2. Clients train, commit, prove, sign, and send envelopes to all aggregators
3. Each aggregator: `verify_envelope` (PQ) → `zk.verify` → keep valid updates only (drop and log rejects with reason)
4. Each aggregator computes the robust aggregate and W_{t+1}; signs a vote on H(W_{t+1}) with ML-DSA
5. Votes are broadcast; a node finalizes when it holds 2f+1 = 3 valid votes for the same hash
6. Clients adopt the finalized W_{t+1}

## Tasks
- [ ] `consensus/messages.py`: Propose, Update, Vote types; all signed
- [ ] `consensus/node.py`: aggregator logic above (asyncio queues as the network)
- [ ] `consensus/fault.py`: faulty-node modes — silent, and equivocating (votes on a wrong hash)
- [ ] `attacks/`: scaled update, forged signature, replayed envelope, proof swapped from another client
- [ ] `demo/run_demo.py`: runs R rounds with flags `--defence on|off --attack ...`, logs accepted/rejected per round

## Tests (`tests/test_integration.py`)
- Benign run finalizes every round
- Each attack is rejected with the expected reason code
- One silent node → still finalizes; one equivocating node → its vote is outvoted
- Two faulty nodes → round does not finalize (shows the bound)

## Exit criteria
- [ ] Full round runs end to end with real PQ + ZK (mock ZK only if Phase 3 fallback 3 applied)
- [ ] All attack and fault tests pass
- [ ] Accuracy with defence on and the attacker present is within ~2 pts of clean baseline

## Deferred
Leader rotation / view change, real networking, partial synchrony, Sybil resistance, secure aggregation.


# MVP Phase 5 — Demo & Proof-of-Work Package (2–3 days)

## Goal
Package evidence that the claim in `00_MVP_Overview.md` holds, reproducibly.

## Tasks
- [ ] Three scenarios, same seed: (A) benign, no attack; (B) poisoned client, plain FedAvg; (C) poisoned client, QuantumShield on
- [ ] `demo/plot.py`: accuracy-vs-round for A/B/C in one figure
- [ ] Overhead table (`demo/results/overheads.md`): signature size, proof size, prove time, verify time, per-round latency, bandwidth per update, with and without QuantumShield
- [ ] Rejection log excerpt showing the attacker's update refused with reason (ZK norm fail), plus a forged-signature rejection
- [ ] One command: `make demo` (or `python -m demo.run_demo --all`) regenerates results and figure
- [ ] README: what it proves, how to run, honest limitations (Δ visible to aggregators; relation is norm+commitment only; simulated network; mock-vs-real ZK status)
- [ ] 5-minute demo script and screen recording
- [ ] One-page results write-up and a "deferred to the full plan" list mapping to `../plan/Phase_*.md`

## Exit criteria
- [ ] A fresh clone reproduces figure and tables with one command
- [ ] Benign accuracy within ~2 pts of baseline; poisoned-with-defence recovers to near baseline
- [ ] Limitations section is explicit about what is not proven

## Next step after MVP
Extend toward the full plan: SGD-step recomputation (Phase 4 Step 4.4), non-IID data and more attacks (Phase 6), scaling benchmarks (Phase 7), paper (Phase 8).