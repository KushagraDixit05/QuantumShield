# p4-E (consensus)
Done: zk_check(verifier) in consensus/node.py (raises ValueError if verifier.zk is None; calls
verifier.verify_envelope(update.envelope, update.delta, update.proof); reasons unchanged).
Node.drop_log() -> [(round, client_id, reason)]; Node.accepted_ids(rnd) -> sorted ids;
Node.votes_by_hash(rnd) -> {h_next: count}. 4 new stubbed-verifier tests (labelled).
Swapped receipt actually returns bad_proof:hash_mismatch (proof_hash check precedes the journal check).
Blocked: none. Needs: none.
Not run: tests/zk (real prover/binaries), deliberately skipped.

tests/test_consensus.py: 11 passed in 0.66s
pytest -q -x --ignore=tests/zk: 115 passed in 37.79s
