"""Negative tests: each attack against plain FedAvg and the plain norm check.
Assertions encode the documented limitations, not just the successes."""
import numpy as np

from attacks import poison
from fl import aggregate as ag
from fl import client, data, model
from fl import fixedpoint as fx
from fl.simulate import load_cfg, run

CFG = load_cfg("configs/mvp.yaml")
B2 = fx.bound_sq(CFG["norm_bound_B"])


def _benign_update(rnd=3, seed=0):
    clients, _ = data.load(seed, 5)
    w = model.init(seed)
    idx = client.sample_indices(seed, rnd, 0, CFG["fl"]["K"], CFG["fl"]["batch"], len(clients[0]))
    return client.local_train(w, clients[0], idx, int(fx.to_fx(CFG["fl"]["lr"])))


def test_B_is_calibrated():
    assert CFG["norm_bound_B"] and CFG["norm_bound_B"] > 0


def test_benign_update_within_bound():
    assert fx.norm_sq(_benign_update(0)) <= B2


def test_scaled_update_rejected_by_norm_bound():
    d = _benign_update()
    assert ag.accepted_by_norm([d, poison.scaled(d, 50)], B2) == [True, False]


def test_scaled_breaks_fedavg_but_not_norm_filter():
    st = {}
    acc_fed = run(CFG, "scaled", "fedavg", 0, B2)
    acc_nf = run(CFG, "scaled", "norm_filter", 0, B2, stats=st)
    benign = run(CFG, "none", "fedavg", 0, B2)
    assert acc_fed[-1] < 0.5 and acc_nf[-1] > benign[-1] - 0.05
    assert st["mal_rejected"] == st["mal_total"] and st["benign_rejected"] == 0


def test_sign_flip_in_bound_not_caught_by_norm_check_and_hurts_fedavg():
    d = _benign_update()
    f = poison.sign_flip(d)
    assert np.array_equal(f, -d) and fx.norm_sq(f) == fx.norm_sq(d)
    assert ag.accepted_by_norm([f], B2) == [True]          # NOT caught
    assert run(CFG, "sign_flip", "fedavg", 0)[-1] < run(CFG, "none", "fedavg", 0)[-1]


def test_sign_flip_amplified_exceeds_bound():
    assert ag.accepted_by_norm([poison.sign_flip(_benign_update(), 20)], B2) == [False]


def test_label_flip_stays_in_bound_not_caught_and_hurts():
    clients, _ = data.load(0, 5)
    bad = poison.label_flip(clients[4])
    assert (bad.y != clients[4].y).all() and np.array_equal(bad.X, clients[4].X)
    st = {}
    acc = run(CFG, "label_flip", "norm_filter", 0, B2, stats=st)
    assert st["mal_rejected"] == 0                          # NOT caught by the norm bound
    assert acc[-1] < run(CFG, "none", "norm_filter", 0, B2)[-1]


def test_replay_is_identical_to_stale_update_and_not_caught_by_fl_layer():
    old, new = _benign_update(0), _benign_update(1)
    r = poison.replay([old, new])
    assert np.array_equal(r, new) and r is not new
    assert poison.replay([]) is None
    assert ag.accepted_by_norm([r], B2) == [True]           # FL layer cannot see staleness


# ---------------------------------------------------------------- envelope-layer attacks (registry)
from pathlib import Path

import pytest

from attacks import envelope_attacks as ea
from attacks.registry import ATTACKS
from fl import merkle
from pq import envelope as ev
from pq import policy, zkpolicy
from pq.session import Session

ROOT = Path(__file__).resolve().parents[1]
ZKDIR = ROOT / "demo" / "results" / "zk"
D = np.arange(2410, dtype=np.int64) % 7 - 3


def _stub_zk():
    return zkpolicy.ZkPolicy(lambda r, e: (True, ""), n_c=[288] * 5, K=2, batch=4, seed=0, lr_fx=19661, B2=10944322663)


def _sess(mode="hybrid", zk=None, t=0):
    roots = [bytes([i]) * 32 for i in range(5)]
    s = Session(mode, "ML-DSA-65", "Ed25519", 5, 4, 1, 5, roots, zk=zk)
    s.begin_round(t, np.zeros(2410, dtype=np.int64))
    return s


def _reason(s, env, d, receipt=None):
    assert s.admit(s.round, 0, env, d, receipt) is False
    return s.drop_log[-1][2]


def test_registry_table_shape():
    assert set(ATTACKS) == {"scaled", "forged", "replay", "swap"}
    assert {a["kind"] for a in ATTACKS.values()} <= {"poison", "envelope"}
    assert all(callable(a["builder"]) and a["expected_reason_prefix"] for a in ATTACKS.values())


# unit test, stubbed verifier, not a proof result
def test_scaled_rejected_without_receipt_and_by_norm_check():
    s = _sess(zk=_stub_zk())
    a = ATTACKS["scaled"]
    env, d, rc = a["builder"](s, 0, 1, D, s=50)
    assert _reason(s, env, d, rc).startswith(a["expected_reason_prefix"])
    assert ag.accepted_by_norm([_benign_update(), d * 1000], B2) == [True, False]


@pytest.mark.parametrize("mode,stripped,reason", [("hybrid", False, "bad_signature"), ("pq", False, "bad_signature"),
                                                  ("hybrid", True, "scheme_downgrade"), ("pq", True, "scheme_downgrade")])
def test_forged_classical_key_rejected_under_pq_and_hybrid(mode, stripped, reason):
    s = _sess(mode)
    env, d, rc = ATTACKS["forged"]["builder"](s, 0, 1, D, stripped=stripped)
    assert _reason(s, env, d, rc) == reason
    if not stripped:
        assert reason.startswith(ATTACKS["forged"]["expected_reason_prefix"])


def test_forged_accepted_under_classical():
    s = _sess("classical")
    env, d, _ = ATTACKS["forged"]["builder"](s, 0, 1, D)
    assert s.admit(0, 1, env, d) is True            # documented limitation: Ed25519 alone is forgeable by Shor


def test_replay_old_envelope_wrong_round_and_same_round_nonce():
    s = _sess("hybrid", t=0)
    env = s.client_envelope(0, 1, D)
    assert s.admit(0, 1, env, D) is True
    r, d, rc = ATTACKS["replay"]["builder"](s, 0, 1, D, env=env)
    assert _reason(s, r, d, rc) == "replayed_nonce"                    # same round, resent verbatim
    s.begin_round(1, np.zeros(2410, dtype=np.int64))
    r, d, rc = ATTACKS["replay"]["builder"](s, 1, 1, D, env=env)
    assert _reason(s, r, d, rc).startswith(ATTACKS["replay"]["expected_reason_prefix"])      # wrong_round


# unit test, stubbed verifier, not a proof result
def test_swap_reasons_with_stub_verifier():
    s = _sess(zk=zkpolicy.ZkPolicy(lambda r, e: (False, "journal_mismatch"), n_c=[288] * 5, K=2, batch=4,
                                   seed=0, lr_fx=19661, B2=10944322663))
    rec_a = b"client-A-receipt-bytes"
    env, d, rc = ATTACKS["swap"]["builder"](s, 0, 1, D, receipt_a=rec_a)
    assert rc is rec_a and ev.parse_update(env.payload)["proof_hash"] == ev.proof_hash(rec_a)
    assert _reason(s, env, d, rc) == ATTACKS["swap"]["expected_reason_prefix"]
    s2 = _sess(zk=_stub_zk())
    env, d, rc = ATTACKS["swap"]["builder"](s2, 0, 1, D, receipt_a=rec_a, hash_matches=False)
    assert _reason(s2, env, d, rc) == ATTACKS["swap"]["variants"]["hash_mismatch"]


# --- real receipts (Phase 3, demo/results/zk/r0_c{0,1}.receipt) through the real verifier; verify only, never prove
def _real_world():
    from zk.bridge import cli
    if not cli.binary().exists() or not (ZKDIR / "r0_c0.receipt").exists():
        pytest.skip("qs-zk binary or Phase 3 receipts missing")
    cfg = {**load_cfg("configs/mvp.yaml"), **load_cfg("configs/phase3.yaml")}
    cfg.pop("base", None)
    seed = int(cfg["seeds"][0])
    clients, _ = data.load(seed, cfg["clients"])
    w = model.init(seed).astype(np.int64)
    pol = zkpolicy.ZkPolicy(cli.verify_receipt, [len(c) for c in clients], cfg["fl"]["K"], cfg["fl"]["batch"], seed,
                            int(fx.to_fx(cfg["fl"]["lr"])), fx.bound_sq(cfg["norm_bound_B"]))
    trees = [merkle.MerkleTree(c.X, c.y) for c in clients]
    s = Session("hybrid", "ML-DSA-65", "Ed25519", cfg["clients"], cfg["aggregators"], seed, cfg.get("epoch_rounds", 5),
                [t.root for t in trees], zk=pol)
    s.begin_round(0, w)
    kw = (cfg["fl"]["K"], cfg["fl"]["batch"], int(fx.to_fx(cfg["fl"]["lr"])), fx.bound_sq(cfg["norm_bound_B"]))
    def delta(c):
        return cli.client_blob(w, clients[c], 0, c, seed, kw[0], kw[1], kw[2], kw[3], ev.make_nonce(seed, 0, c), trees[c])[1]
    return s, delta


def test_swap_real_receipt_other_client_journal_mismatch():
    """Client 1's envelope + delta with client 0's REAL round-0 receipt, through the real verifier (verify only)."""
    s, delta = _real_world()
    rec_a = (ZKDIR / "r0_c0.receipt").read_bytes()
    env, d, rc = ATTACKS["swap"]["builder"](s, 0, 1, delta(1), receipt_a=rec_a)
    assert s.admit(0, 1, env, d, rc) is False
    assert s.drop_log[-1][2] == "bad_proof:journal_mismatch"


def test_honest_real_receipt_accepted_control():
    s, delta = _real_world()
    rec = (ZKDIR / "r0_c0.receipt").read_bytes()
    assert s.admit(0, 0, s.client_envelope(0, 0, delta(0), rec), delta(0), rec) is True
