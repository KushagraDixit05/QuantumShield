"""Tests on the ONE honest real receipt (client 0, round 0). Everything after the first fixture use is a
cheap verify call. No stubs, no dev mode."""
import time

import numpy as np
import pytest

from fl import zk_reference as zr
from pq import envelope as ev
from pq import zkpolicy
from zk.bridge import cli

from conftest import run_verify

pytestmark = pytest.mark.real_proof

FIELDS = [("relation", 5, 1), ("t", 6, 4), ("c", 10, 4), ("n_c", 14, 4), ("K", 18, 4), ("batch", 22, 4),
          ("seed", 26, 8), ("lr_fx", 34, 8), ("B2", 42, 8), ("H_w", 50, 32), ("C", 82, 32), ("R", 114, 32)]


def pub_from_envelope(world, env):
    p = ev.parse_update(env.payload)
    return zkpolicy.expected_public(1, p["round"], p["client_id"], len(world.clients[p["client_id"]]), world.K,
                                    world.batch, world.seed, world.lr_fx, world.B2, p["h_w"], p["c"], p["r"])


def test_positive_honest_receipt_admitted_and_bound(world, honest, tmp_path):
    ref_ok, ref_journal, _ = zr.evaluate(honest.blob)
    assert ref_ok and honest.journal == ref_journal == honest.blob[:146]
    sess = world.session()
    env = sess.client_envelope(0, 0, honest.delta, honest.receipt)
    assert len(env.sigs) == 2 and ev.parse_update(env.payload)["version"] == 2     # hybrid-signed v2
    exp = pub_from_envelope(world, env)
    assert exp == honest.journal, "expected_public from the SIGNED envelope fields != receipt journal"
    code, err = run_verify(honest.receipt, exp, tmp_path)
    assert code == 0, err
    t0 = time.time()
    assert sess.admit(0, 0, env, honest.delta, honest.receipt) is True
    print(f"[admit] Session.admit with real receipt: {time.time() - t0:.2f}s, receipt_bytes={len(honest.receipt)}, "
          f"image_id={honest.image_id[:16]}..., prove_s={honest.stats.get('prove_s')} (cached={honest.cached})")
    assert sess.dropped == {}


def test_receipt_leaks_no_delta_or_nonce(world, honest):
    nonce = ev.make_nonce(world.seed, 0, 0)
    delta_head = np.asarray(honest.delta[:8], dtype="<i8").tobytes()
    assert len(delta_head) == 64 and honest.delta[:8].any()
    for name, blob in [("receipt", honest.receipt), ("journal", honest.journal)]:
        assert delta_head not in blob, f"delta bytes found in {name}"
        assert nonce not in blob, f"nonce found in {name}"
    assert len(honest.journal) == 146 and honest.journal == honest.blob[:146]       # public part only


@pytest.mark.parametrize("name,off,size", FIELDS)
def test_tampered_public_input_is_journal_mismatch(honest, name, off, size, tmp_path):
    ok, why = cli.verify_receipt(honest.receipt, honest.journal)
    assert (ok, why) == (True, "ok")
    exp = bytearray(honest.journal)
    if name == "relation":
        exp[off] = 2
    else:
        exp[off] ^= 1
    code, err = run_verify(honest.receipt, bytes(exp), tmp_path)
    res = cli.verify_receipt(honest.receipt, bytes(exp))
    print(f"[tamper public {name}] qs-zk verify exit={code} -> {res}")
    assert code == 5 and res == (False, "journal_mismatch")


def test_tampered_receipt_bytes_receipt_invalid(honest, tmp_path):
    rb, j = honest.receipt, honest.journal
    jpos = rb.find(j)
    assert jpos > 0, "journal not found inside receipt bytes"
    variants = {"seal_middle": len(rb) // 2, "seal_early": 64, "journal_region": jpos + 100, "last_byte": len(rb) - 1}
    for name, pos in variants.items():
        b = bytearray(rb); b[pos] ^= 0x01
        code, err = run_verify(bytes(b), j, tmp_path)
        print(f"[tamper receipt {name} @{pos}] exit={code} {err[:120]}")
        assert code == 4, (name, code, err)
    code, err = run_verify(rb[: len(rb) // 2], j, tmp_path)
    print(f"[truncated receipt] exit={code} {err[:120]}")
    assert code == 4


def test_swapped_proof_other_client_journal_mismatch(world, honest):
    """Receipt of client 0 / round 0 presented in client 1's round-0 envelope (client 1's own delta, so the
    commitment and signature checks pass and the ZkPolicy layer is what fires)."""
    sess = world.session()
    _, d1 = world.blob(0, 1)
    env = sess.client_envelope(0, 1, d1, honest.receipt)
    assert sess.admit(0, 1, env, d1, honest.receipt) is False
    print("[swapped proof] ->", sess.drop_log[-1])
    assert sess.drop_log[-1] == (0, 1, "bad_proof:journal_mismatch")


def test_proof_hash_of_different_receipt_hash_mismatch(world, honest):
    other = bytearray(honest.receipt); other[len(other) // 2] ^= 1                  # a different receipt blob
    sess = world.session()
    env = sess.client_envelope(0, 0, honest.delta, bytes(other))                    # proof_hash = H(other)
    assert sess.admit(0, 0, env, honest.delta, honest.receipt) is False
    print("[hash mismatch] ->", sess.drop_log[-1])
    assert sess.drop_log[-1] == (0, 0, "bad_proof:hash_mismatch")


def test_v1_envelope_missing_proof_hash_with_real_receipt(world, honest):
    sess = world.session()
    env = sess.client_envelope(0, 0, honest.delta)                                  # v1
    assert sess.admit(0, 0, env, honest.delta, honest.receipt) is False
    assert sess.drop_log[-1] == (0, 0, "bad_proof:missing_proof_hash")


def test_wrong_round_both_layers(world, honest):
    # Layer 1: Verifier check order. The honest round-0 envelope arrives when the aggregator is in round 1:
    # `wrong_round` fires first, the ZK policy is never reached.
    sess = world.session()
    env0 = sess.client_envelope(0, 0, honest.delta, honest.receipt)
    sess.begin_round(1, world.w)
    assert sess.admit(1, 0, env0, honest.delta, honest.receipt) is False
    print("[wrong round, Verifier layer] ->", sess.drop_log[-1])
    assert sess.drop_log[-1][2] == "wrong_round"
    # Layer 2: the client re-signs the SAME nonce/delta/receipt in a round-1 envelope (round-1 signature
    # valid, same H(W), so the Verifier accepts it up to the policy). Only t differs from the journal, so
    # ZkPolicy fires with journal_mismatch.
    nonce0 = ev.make_nonce(world.seed, 0, 0)
    env1 = ev.sign_update(sess.registry, sess.algs, 1, 0, sess.h_w, honest.delta, world.trees[0].root, nonce0,
                          ev.proof_hash(honest.receipt))
    assert sess.admit(1, 0, env1, honest.delta, honest.receipt) is False
    print("[wrong round, ZkPolicy layer (t only differs)] ->", sess.drop_log[-1])
    assert sess.drop_log[-1] == (1, 0, "bad_proof:journal_mismatch")
    # Layer 2b: the natural round-1 envelope (fresh round-1 nonce) differs in t and C: also journal_mismatch.
    env1b = sess.client_envelope(1, 0, honest.delta, honest.receipt)
    assert sess.admit(1, 0, env1b, honest.delta, honest.receipt) is False
    print("[wrong round, natural round-1 envelope (t and C differ)] ->", sess.drop_log[-1])
    assert sess.drop_log[-1] == (1, 0, "bad_proof:journal_mismatch")
