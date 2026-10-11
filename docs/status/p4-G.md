# p4-G (integration tests)
Done: tests/test_integration.py (14 tests). Hybrid signatures (Ed25519 + ML-DSA-65), 4 nodes, zk_check hook.
Attacks built with Agent F's attacks.registry.ATTACKS (scaled, forged, forged stripped, replay, swap x2).
Fast tests use a stubbed receipt verifier (each labelled `# unit test, stubbed verifier, not a proof result`);
the stub accepts b"stub-receipt-c<id>" only for client <id>'s journal.
Real-receipt test: demo/results/zk/r0_c0.receipt through real cli.verify_receipt via zk_check (verify only), passes (not skipped).
Observed codes: scaled -> bad_proof:missing_proof_hash; forged -> bad_signature; forged stripped -> scheme_downgrade;
replay next round -> wrong_round; replay same round -> replayed_nonce; swap -> bad_proof:journal_mismatch;
swap with non-matching hash -> bad_proof:hash_mismatch. Never in accepted_ids; honest nodes still finalize.
Blocked: none. Needs: none. Prover never run, RISC0_DEV_MODE never set.

$ .venv/bin/python -m pytest tests/test_integration.py -q
..............                                                           [100%]
14 passed in 2.45s
