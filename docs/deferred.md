# Deferred to the full plan

The approved plan in `plan/` contains only MVP phases (D-005). "Full plan" below refers to the Deferred column of `plan/00_MVP_Overview.md` section 2 and the "Next step after MVP" line of `plan/MVP_Phase_5_Demo_and_Proof_of_Work.md`. The brief's Phase 4 and Phase 5 do not match the approved plan; the MVP plan was followed and the brief-only items are deferred (D-020).

## From the MVP plan's Deferred column
| Item | Plan reference | Status |
|---|---|---|
| Non-IID data, CIFAR-10, larger models | 00_MVP_Overview.md s2; Phase 6 in Phase 5's "next step" | Not started |
| Full attack suite, adaptive attackers | same | Four data attacks and two envelope attacks exist; no adaptive attacker |
| Scaling benchmarks, ablations | Phase 7 in the next-step line | Not started |
| Paper | Phase 8 in the next-step line | Not started |
| Real network, full HotStuff/PBFT | 00_MVP_Overview.md s2 | Not started |
| Secure aggregation / DP | 00_MVP_Overview.md s2 | Not started |
| SGD recompute at plan scale | MVP_Phase_5 next step (Phase 4 Step 4.4) | Done at K=4, batch 8 only; K=20, batch 32 is deferred (D-019) |

## Brief-only items (D-020)
- View change, leader rotation, partial synchrony
- Network simulator beyond the in-process asyncio one
- n=7, 10, 16 aggregators (only n=4, f=1 is run)
- Certificate ledger
- Non-IID partitions
- Evaluation experiments E1-E7 and ablations
- ZK scaling to about 100k parameters (measured only for the 2,410-parameter model)
- Falcon / SLH-DSA at scale: Falcon-512, SLH-DSA-128s and hybrid are implemented and micro-benchmarked (`demo/results/sig_bench.md`), but not used in FL runs or consensus; the demo uses ML-DSA-65 + Ed25519.
- Per-epoch key rotation exists in code (D-014) but is not exercised at scale.

## Smaller gaps inside the MVP
- Registered Merkle roots / attested datasets (limitations item 5).
- Real proofs for all client-rounds of a scenario run (about 5 h for 50 updates at K=4; far more at K=20).
- Secret-key distribution and a real PKI.
- The recorded screen capture: only the script exists (`docs/demo_script.md`).
