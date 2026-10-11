# p4-F status (attacks)

## Done
- attacks/envelope_attacks.py: `swap_proof(session, t, client_b, d_b, receipt_a, hash_matches=True)` -> (env, delta, receipt) as the aggregator receives it.
- attacks/registry.py: `ATTACKS` {scaled, forged, replay, swap}: kind, builder, expected_reason_prefix, variants.
  Reasons observed by running: scaled -> bad_proof:missing_proof_hash (v1 envelope; missing_receipt if hash signed but no receipt);
  forged -> bad_signature (junk PQ sig) / scheme_downgrade (stripped), accepted under classical; replay -> wrong_round (later round) / replayed_nonce (same round);
  swap -> bad_proof:journal_mismatch (hash matches) / bad_proof:hash_mismatch (A's bytes, B's hash).
- tests/test_attacks.py: 19 tests. Stubbed-verifier tests carry the required comment. Two use the REAL verifier on existing
  demo/results/zk/r0_c0.receipt (verify only, ~0.2 s, no prover, no dev mode): swap -> journal_mismatch, and an honest control accepted.
  They skip if the qs-zk binary or receipt is missing.

## Blocked
- None.

## Needs (other owners)
- Scaled-update norm rejection in the ZK path only shows as missing_proof_hash/missing_receipt (attacker cannot prove); no real receipt of a scaled update can exist.

## Output
$ .venv/bin/python -m pytest tests/test_attacks.py -q
...................                                                      [100%]
19 passed in 3.94s
