import pytest

from backend import reasons

CASES = [
    ("bad_signature", "bad_signature", "signature"), ("scheme_downgrade", "bad_signature", "signature"),
    ("unsigned", "bad_signature", "signature"), ("unknown_key", "bad_signature", "signature"),
    ("revoked_key", "bad_signature", "signature"), ("key_identity_mismatch", "bad_signature", "signature"),
    ("wrong_round", "wrong_round", "signature"), ("wrong_model_hash", "wrong_round", "signature"),
    ("norm_bound_exceeded", "norm_bound_exceeded", "plaintext_norm_gate"),
    ("bad_proof:missing_proof_hash", "bad_proof", "zk"), ("bad_proof:journal_mismatch", "bad_proof", "zk"),
    ("replayed_nonce", "replay", "signature"), ("duplicate_submission", "replay", "signature"),
    ("stale_key", "replay", "signature"),
    ("not_in_quorum", "not_in_quorum", "consensus"),
    ("commitment_mismatch", "other", "signature"), ("something_new", "other", "signature"),
]


@pytest.mark.parametrize("raw,reason,gate", CASES)
def test_mapping(raw, reason, gate):
    r = reasons.rejection(3, 4, raw)
    assert (r["reason"], r["gate"], r["raw_reason"]) == (reason, gate, raw)
    assert r["round"] == 3 and r["client"] == 4 and r["reason"] in reasons.REASONS


def test_quorum_rejection_has_null_client():
    assert reasons.rejection(2, None, "not_in_quorum")["client"] is None
