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
