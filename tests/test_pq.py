"""Signature wrapper, envelope, verifier. Real liboqs / cryptography signatures throughout."""
import numpy as np
import pytest

from pq import envelope as ev
from pq import policy, sig, votes
from pq import registry as rg

ALL = list(sig.SCHEMES)
PQ_DEFAULT = "ML-DSA-65"
H_W = bytes(range(32))
ROOT = bytes(32)


def mkdelta(seed=0):
    return np.random.default_rng(seed).integers(-5000, 5000, 2410, dtype=np.int64)


def setup(mode="pq", pq_alg=PQ_DEFAULT, rnd=0, epoch_rounds=5, seed=1):
    reg = rg.KeyRegistry(5, 4, ["Ed25519", pq_alg], seed, epoch_rounds)
    v = policy.Verifier(reg, mode, pq_alg)
    v.begin_round(rnd, H_W)
    return reg, v


def upd(reg, v, client=1, rnd=0, d=None, h_w=H_W, nonce=None, algs=None):
    d = mkdelta() if d is None else d
    nonce = ev.make_nonce(1, rnd, client) if nonce is None else nonce
    return ev.sign_update(reg, v.required if algs is None else algs, rnd, client, h_w, d, ROOT, nonce), d


# ---- positive ----
@pytest.mark.parametrize("alg", ALL)
def test_every_algorithm_signs_and_verifies(alg):
    pk, sk = sig.keygen(alg)
    msg = b"quantumshield"
    s = sig.sign(alg, sk, msg)
    assert sig.verify(alg, pk, msg, s)
    assert not sig.verify(alg, pk, msg + b"x", s)
    bad = bytearray(s); bad[len(bad) // 2] ^= 1
    assert not sig.verify(alg, pk, msg, bytes(bad))
    assert not sig.verify(alg, pk, msg, s[:-1]) and not sig.verify(alg, pk, msg, b"")   # no exception
    assert not sig.verify(alg, pk[:-1], msg, s)
    pk2, _ = sig.keygen(alg)
    assert not sig.verify(alg, pk2, msg, s)                                              # wrong key


@pytest.mark.parametrize("alg", ALL)
def test_seeded_keys_and_signatures_reproducible(alg):
    out = []
    for _ in range(2):
        sig.seed_rng(42)
        pk, sk = sig.keygen(alg)
        out.append((pk, sk, sig.sign(alg, sk, b"m")))
    sig.seed_rng(None)
    assert out[0] == out[1]


@pytest.mark.parametrize("mode", ["classical", "pq", "hybrid"])
@pytest.mark.parametrize("pq_alg", ["ML-DSA-44", "ML-DSA-65", "Falcon-512", "SLH-DSA-128s"])
def test_valid_update_accepted(mode, pq_alg):
    reg, v = setup(mode, pq_alg)
    env, d = upd(reg, v)
    assert v.verify_envelope(env, d) == (True, "ok")
    assert env.sigs and len(env.sigs) == (2 if mode == "hybrid" else 1)


def test_wire_roundtrip_and_malformed():
    reg, v = setup("hybrid")
    env, d = upd(reg, v)
    back = ev.Envelope.from_wire(env.wire(), ev.UPDATE_LEN)
    assert back == env and v.verify_envelope(back, d)[0]
    assert ev.Envelope.from_wire(env.wire()[:-3], ev.UPDATE_LEN) is None
    assert ev.Envelope.from_wire(b"", ev.UPDATE_LEN) is None


# ---- negative ----
@pytest.mark.parametrize("mode", ["classical", "pq", "hybrid"])
def test_tampered_payload_rejected(mode):
    reg, v = setup(mode)
    env, d = upd(reg, v)
    for pos in (2 + 4 + 4 + 64 + 3, ev.UPDATE_LEN - 1, 10):    # C_i byte, nonce byte, H(W_t) byte
        p = bytearray(env.payload); p[pos] ^= 1
        ok, reason = v.verify_envelope(ev.Envelope(bytes(p), env.sigs), d)
        assert not ok and reason in ("bad_signature", "wrong_model_hash", "commitment_mismatch")
    p = bytearray(env.payload); p[ev.UPDATE_LEN - 5] ^= 1       # nonce: signature must catch it
    assert v.verify_envelope(ev.Envelope(bytes(p), env.sigs), d) == (False, "bad_signature")


def test_tampered_delta_rejected_despite_valid_signature():
    reg, v = setup("pq")
    env, d = upd(reg, v)
    d2 = d.copy(); d2[7] += 1
    assert v.verify_envelope(env, d2) == (False, "commitment_mismatch")
    assert v.verify_envelope(env, d) == (True, "ok")             # the failed attempt burned no nonce


def test_wrong_round_rejected():
    reg, v = setup("pq", rnd=3)
    env, d = upd(reg, v, rnd=2)
    assert v.verify_envelope(env, d) == (False, "wrong_round")
    env, d = upd(reg, v, rnd=4)
    assert v.verify_envelope(env, d) == (False, "wrong_round")


def test_wrong_model_hash_rejected():
    reg, v = setup("hybrid")
    env, d = upd(reg, v, h_w=bytes(32))
    assert v.verify_envelope(env, d) == (False, "wrong_model_hash")


def test_replayed_nonce_rejected():
    reg, v = setup("pq")
    env, d = upd(reg, v)
    assert v.verify_envelope(env, d)[0]
    assert v.verify_envelope(env, d) == (False, "replayed_nonce")      # same envelope again, same round
    # fresh envelope, but the client reuses its old nonce in a later round
    v.begin_round(1, H_W)
    env2, d2 = upd(reg, v, rnd=1, nonce=ev.make_nonce(1, 0, 1))
    assert v.verify_envelope(env2, d2) == (False, "replayed_nonce")
    # a second, different submission in the same round
    v.begin_round(2, H_W)
    a, da = upd(reg, v, rnd=2); b, db = upd(reg, v, rnd=2, nonce=bytes([9]) * 32, d=mkdelta(5))
    assert v.verify_envelope(a, da)[0]
    assert v.verify_envelope(b, db) == (False, "duplicate_submission")


def test_old_envelope_resent_next_round_rejected():
    reg, v = setup("pq")
    env, d = upd(reg, v)
    assert v.verify_envelope(env, d)[0]
    v.begin_round(1, H_W)
    assert v.verify_envelope(env, d) == (False, "wrong_round")


@pytest.mark.parametrize("mode", ["classical", "pq", "hybrid"])
def test_wrong_key_rejected(mode):
    reg, v = setup(mode)
    other = rg.KeyRegistry(5, 4, ["Ed25519", PQ_DEFAULT], seed=999, epoch_rounds=5)   # attacker's own PKI
    payload = ev.pack_update(0, 1, H_W, ev.commit(mkdelta(), bytes(32)), ROOT, bytes(32))
    env = ev.sign_payload(other, "client", 1, v.required, payload)                    # right key ids, wrong keys
    assert v.verify_envelope(env, mkdelta()) == (False, "bad_signature")
    # signed by a different client's genuine key but claiming client 1
    env2 = ev.sign_payload(reg, "client", 2, v.required, payload)
    assert v.verify_envelope(env2, mkdelta()) == (False, "key_identity_mismatch")


def test_revoked_key_rejected_and_other_clients_unaffected():
    reg, v = setup("hybrid")
    env, d = upd(reg, v, client=1)
    ok_env, ok_d = upd(reg, v, client=2)
    reg.revoke(reg.key_id("client", 1, PQ_DEFAULT))                      # revoking either key suffices
    assert v.verify_envelope(env, d) == (False, "revoked_key")
    assert v.verify_envelope(ok_env, ok_d)[0]


def test_rotation_retires_old_keys():
    reg, v = setup("pq", epoch_rounds=5)
    old, d = upd(reg, v, rnd=0)
    reg.advance_to_round(5)
    v.begin_round(5, H_W)
    assert reg.epoch == 1
    assert v.verify_envelope(old, d)[1] in ("stale_key",)
    new, d2 = upd(reg, v, rnd=5)
    assert v.verify_envelope(new, d2) == (True, "ok")
    assert reg.key_id("client", 1, PQ_DEFAULT).split(":")[2] == "1"


def test_downgrade_hybrid_to_classical_rejected():
    reg, v = setup("hybrid")
    env, d = upd(reg, v, algs=["Ed25519"])                               # PQ signature stripped
    assert v.verify_envelope(env, d) == (False, "scheme_downgrade")
    env, d = upd(reg, v, algs=[PQ_DEFAULT])
    assert v.verify_envelope(env, d) == (False, "scheme_downgrade")
    env, d = upd(reg, v, algs=[])
    assert v.verify_envelope(env, d) == (False, "unsigned")
    # and a classical-only deployment refuses a PQ-only or hybrid envelope too (exact scheme set)
    _, vc = setup("classical")
    assert vc.verify_envelope(*upd(reg, vc, algs=["Ed25519", PQ_DEFAULT]))[1] == "scheme_downgrade"


def test_pq_mode_rejects_ed25519_only_envelope():
    reg, v = setup("pq")
    assert v.verify_envelope(*upd(reg, v, algs=["Ed25519"]))[1] == "scheme_downgrade"


def test_signature_does_not_transfer_between_algorithm_labels():
    reg, v = setup("pq")
    env, d = upd(reg, v)
    alg, kid, s = env.sigs[0]
    relabeled = ev.Envelope(env.payload, [("ML-DSA-44", kid, s)])
    assert not v.verify_envelope(relabeled, d)[0]


# ---- votes ----
def test_vote_sign_verify_and_domain_separation():
    reg, v = setup("hybrid")
    vote = votes.sign_vote(reg, v.required, 0, 2, H_W, [0, 1, 2], seed=1)
    assert v.verify_vote(vote) == (True, "ok")
    assert v.verify_vote(vote) == (False, "replayed_nonce")
    assert v.verify_envelope(vote, mkdelta())[1] == "wrong_kind"        # a vote is not an update
    e, d = upd(reg, v)
    assert v.verify_vote(e)[1] == "wrong_kind"                          # an update is not a vote
    # re-tag attack: take a vote signature, present the bytes as an update payload of the same kind byte
    forged_payload = bytearray(vote.payload); forged_payload[1] = ev.KIND_UPDATE
    assert not v.verify_vote(ev.Envelope(bytes(forged_payload), vote.sigs))[0]
    # vote signed by a client key is refused
    payload = ev.pack_vote(0, 2, H_W, bytes(32), bytes([7]) * 32)
    bad = ev.sign_payload(reg, "client", 2, v.required, payload)
    assert not v.verify_vote(bad)[0]


def test_vote_wrong_round_and_tamper():
    reg, v = setup("pq")
    vote = votes.sign_vote(reg, v.required, 1, 0, H_W, [0], seed=1)
    assert v.verify_vote(vote) == (False, "wrong_round")
    v.begin_round(1, H_W)
    p = bytearray(vote.payload); p[20] ^= 1
    assert v.verify_vote(ev.Envelope(bytes(p), vote.sigs)) == (False, "bad_signature")


def test_none_mode_is_explicit_and_disables_checks():
    reg, v = setup("none")
    assert v.verify_envelope(ev.Envelope(b"junk"), mkdelta()) == (True, "signatures_disabled")
