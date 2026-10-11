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
