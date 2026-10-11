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
