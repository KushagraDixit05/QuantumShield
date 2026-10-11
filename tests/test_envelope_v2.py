"""Envelope v2 (proof_hash) and the aggregator-side proof policy.

These tests check the binding logic only: the hash match, the journal the aggregator builds from the
signed envelope, and the ordering of checks. The `verify_receipt` callable here is a recording stub
(NOT a verifier and not a proof); real receipts are verified in tests/zk/.
"""
import numpy as np

from pq import envelope as ev
from pq import policy, zkpolicy
from pq import registry as rg

H_W, ROOT = bytes(range(32)), bytes(range(32, 64))
RECEIPT = b"receipt-bytes-placeholder"


def setup(verify):
    reg = rg.KeyRegistry(5, 4, ["Ed25519", "ML-DSA-65"], 1, 5)
    zk = zkpolicy.ZkPolicy(verify, n_c=[288] * 5, K=2, batch=4, seed=0, lr_fx=19661, B2=10944322663)
    v = policy.Verifier(reg, "hybrid", "ML-DSA-65", zk=zk)
    v.begin_round(0, H_W)
    return reg, v


def env_for(reg, v, receipt=RECEIPT, delta=None, client=1, ph="auto"):
    d = np.arange(2410, dtype=np.int64) if delta is None else delta
    ph = ev.proof_hash(receipt) if ph == "auto" else ph
    return ev.sign_update(reg, v.required, 0, client, H_W, d, ROOT, ev.make_nonce(1, 0, client), ph), d


def test_v2_roundtrip_and_v1_still_parses():
    reg, v = setup(lambda r, e: (True, ""))
    env, _ = env_for(reg, v)
    p = ev.parse_update(env.payload)
    assert p["version"] == 2 and p["proof_hash"] == ev.proof_hash(RECEIPT) and len(env.payload) == ev.UPDATE_LEN_V2
    v1 = ev.pack_update(0, 1, H_W, bytes(32), ROOT, bytes(32))
    assert ev.parse_update(v1)["proof_hash"] is None and ev.parse_update(v1 + b"x") is None


def test_journal_is_built_from_signed_envelope_fields():
    seen = []
    reg, v = setup(lambda r, e: (seen.append(e), (True, ""))[1])
    env, d = env_for(reg, v)
    assert v.verify_envelope(env, d, RECEIPT) == (True, "ok")
    j = seen[0]
    assert len(j) == zkpolicy.JOURNAL_LEN and j[:6] == b"QSZK\x01\x01"
    assert j[50:82] == H_W and j[82:114] == ev.commit(d, ev.make_nonce(1, 0, 1)) and j[114:] == ROOT


def test_missing_swapped_or_absent_receipt_rejected():
    reg, v = setup(lambda r, e: (True, ""))
    env, d = env_for(reg, v)
    assert v.verify_envelope(env, d, None) == (False, "bad_proof:missing_receipt")
    assert v.verify_envelope(env, d, RECEIPT + b"!") == (False, "bad_proof:hash_mismatch")
    v1 = ev.sign_update(reg, v.required, 0, 2, H_W, d, ROOT, ev.make_nonce(1, 0, 2))   # v1: no proof_hash
    assert v.verify_envelope(v1, d, RECEIPT) == (False, "bad_proof:missing_proof_hash")


def test_verifier_failure_reason_is_reported_and_nonce_not_burned():
    ok = {"v": False}
    reg, v = setup(lambda r, e: (ok["v"], "journal_mismatch"))
    env, d = env_for(reg, v)
    assert v.verify_envelope(env, d, RECEIPT) == (False, "bad_proof:journal_mismatch")
    ok["v"] = True
    assert v.verify_envelope(env, d, RECEIPT) == (True, "ok")


def test_tampered_delta_caught_before_proof_check():
    called = []
    reg, v = setup(lambda r, e: (called.append(1), (True, ""))[1])
    env, d = env_for(reg, v)
    d2 = d.copy(); d2[0] += 1
    assert v.verify_envelope(env, d2, RECEIPT) == (False, "commitment_mismatch") and not called


def test_zk_with_signatures_none_is_refused():
    import pytest
    reg = rg.KeyRegistry(5, 4, ["Ed25519", "ML-DSA-65"], 1, 5)
    zk = zkpolicy.ZkPolicy(lambda r, e: (True, ""), [288] * 5, 2, 4, 0, 19661, 10944322663)
    with pytest.raises(ValueError):
        policy.Verifier(reg, "none", "ML-DSA-65", zk=zk)


def test_relation_2_policy_needs_explicit_cut_flag():
    import pytest
    with pytest.raises(ValueError):
        zkpolicy.ZkPolicy(lambda r, e: (True, ""), [288], 0, 0, 0, 1, 1, relation=2)
    zkpolicy.ZkPolicy(lambda r, e: (True, ""), [288], 0, 0, 0, 1, 1, relation=2, allow_cut=True)


def test_unregistered_root_rejected():
    reg = rg.KeyRegistry(5, 4, ["Ed25519", "ML-DSA-65"], 1, 5)
    zk = zkpolicy.ZkPolicy(lambda r, e: (True, ""), [288] * 5, 2, 4, 0, 19661, 10944322663, roots=[bytes(32)] * 5)
    v = policy.Verifier(reg, "hybrid", "ML-DSA-65", zk=zk)
    v.begin_round(0, H_W)
    env, d = env_for(reg, v)                              # envelope carries ROOT, registry says zeros
    assert v.verify_envelope(env, d, RECEIPT) == (False, "bad_proof:unregistered_root")


def test_replay_is_rejected_before_proof_check():
    calls = []
    reg, v = setup(lambda r, e: (calls.append(1), (True, ""))[1])
    env, d = env_for(reg, v)
    assert v.verify_envelope(env, d, RECEIPT)[0] and len(calls) == 1
    assert v.verify_envelope(env, d, RECEIPT) == (False, "replayed_nonce") and len(calls) == 1
