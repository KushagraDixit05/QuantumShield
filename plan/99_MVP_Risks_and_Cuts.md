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
