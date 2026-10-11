"""Phase 4 integration: signed clients -> 4 consensus-lite aggregators (f=1), attacks, faults.

Fast tests use a STUBBED receipt verifier (clearly labelled); the one real-receipt test calls the real
`qs-zk verify` on an existing Phase 3 receipt. The prover is never run and RISC0_DEV_MODE is never set.
"""
import asyncio
from pathlib import Path

import numpy as np
import pytest

from attacks import poison
from attacks.registry import ATTACKS
from consensus import fault
from consensus.messages import Update
from consensus.node import Network, Node, run_round, run_rounds_with, zk_check
from fl import fixedpoint as fx
from pq import envelope as ev
from pq import policy, zkpolicy
from pq.session import Session

N, F, N_CLIENTS, DIM = 4, 1, 5, 16
ZKDIR = Path(__file__).resolve().parents[1] / "demo" / "results" / "zk"
B2 = 4 * 16 * 16 * 4          # honest deltas (|x|<=4, DIM=16) have norm_sq <= 256 << B2; scaled x50 is far above


def _stub_verify(receipt, expected):
    """Stub of the real verifier: receipt b'stub-receipt-c<id>' is valid only for client <id>'s journal
    (journal layout: 'QSZK', 2 bytes, t u32, c u32, ...)."""
    cid = int.from_bytes(expected[10:14], "little")
    if receipt == b"stub-receipt-c%d" % cid:
        return True, "ok"
    return False, "journal_mismatch"


def rec(c):
    return b"stub-receipt-c%d" % c


class Rig:
    """One shared key registry (inside a Session used as the client-side signer) and 4 nodes, each with its
    own stateful Verifier + zk_check hook."""

    def __init__(self, faults=None, mode="hybrid"):
        zk = zkpolicy.ZkPolicy(_stub_verify, n_c=[10] * N_CLIENTS, K=1, batch=1, seed=1, lr_fx=1, B2=B2)
        roots = [bytes([i]) * 32 for i in range(N_CLIENTS)]
        self.s = Session(mode, "ML-DSA-65", "Ed25519", N_CLIENTS, N, 1, 100, roots, zk=zk)
        self.reg, self.algs = self.s.registry, self.s.algs
        self.net = Network(N)
        self.nodes = []
        for i in range(N):
            v = policy.Verifier(self.reg, mode, "ML-DSA-65", "Ed25519", zk=zk)
            self.nodes.append(Node(i, N, F, self.reg, v, self.net, verify_update=zk_check(v), seed=1,
                                   fault_mode=(faults or {}).get(i, fault.HONEST)))
        self.honest = [n for n in self.nodes if n.fault == fault.HONEST]
        self.w = np.zeros(DIM, dtype=np.int64)
        self.rng = np.random.default_rng(0)

    def honest_updates(self, rnd, only=None):
        self.s.begin_round(rnd, self.w)
        ups = []
        for c in (only if only is not None else range(N_CLIENTS)):
            d = self.rng.integers(-4, 5, DIM).astype(np.int64)
            ups.append(Update(c, self.s.client_envelope(rnd, c, d, rec(c)), d, rec(c)))
        return ups

    def play(self, rounds_updates):
        """rounds_updates: callable(rnd) -> list of Update. Returns per-round list of honest finalized entries."""
        out = []

        async def body():
            for r, ups_fn in enumerate(rounds_updates):
                ups = ups_fn(r)
                await run_round(self.nodes, self.net, self.reg, self.algs, r, self.w, ups)
                fin = [n.finalized.get(r) for n in self.honest]
                out.append(fin)
                if fin[0]:
                    self.w = fin[0][1]
        asyncio.run(run_rounds_with(self.nodes, self.net, body))
        return out


def one_round(rig, mutate=None, rounds=1):
    def fn(r):
        ups = rig.honest_updates(r)
        if mutate:
            ups = mutate(rig, r, ups)
        return ups
    return rig.play([fn] * rounds)


# ---------------- benign / determinism ----------------
def test_benign_finalizes_every_round_at_every_honest_node_same_hash():
    # unit test, stubbed verifier, not a proof result
    rig = Rig()
    fins = one_round(rig, rounds=3)
    for fin in fins:
        assert all(f is not None for f in fin)
        assert len({f[0] for f in fin}) == 1                        # determinism: one hash across honest nodes
        assert len({f[1].tobytes() for f in fin}) == 1
    for n in rig.nodes:
        assert n.drop_log() == [] and not n.bad_votes
        assert all(n.accepted_ids(r) == list(range(N_CLIENTS)) for r in range(3))


# ---------------- attacks ----------------
def _attack_round(mutate):
    rig = Rig()
    fins = one_round(rig, mutate)
    return rig, fins


def _assert_dropped(rig, fins, victim, code):
    for n in rig.nodes:
        assert n.drop_log() == [(0, victim, code)]
        assert victim not in n.accepted_ids(0)
        assert n.accepted_ids(0) == [c for c in range(N_CLIENTS) if c != victim]
    assert all(f is not None for f in fins[0]) and len({f[0] for f in fins[0]}) == 1   # honest still finalize


def test_scaled_update_over_norm_bound_is_dropped():
    # unit test, stubbed verifier, not a proof result
    def m(rig, r, ups):
        base = ups[2].delta
        env, d, rc = ATTACKS["scaled"]["builder"](rig.s, r, 2, base)
        assert fx.norm_sq(d) > B2 >= fx.norm_sq(base)               # really over the bound
        ups[2] = Update(2, env, d, rc)
        return ups
    rig, fins = _attack_round(m)
    _assert_dropped(rig, fins, 2, "bad_proof:missing_proof_hash")   # no proof exists for an over-bound update


def test_forged_classical_key_signature_dropped_under_hybrid():
    # unit test, stubbed verifier, not a proof result
    def m(rig, r, ups):
        env, d, rc = ATTACKS["forged"]["builder"](rig.s, r, 1, ups[1].delta)
        ups[1] = Update(1, env, d, rec(1))
        return ups
    rig, fins = _attack_round(m)
    _assert_dropped(rig, fins, 1, "bad_signature")


def test_forged_stripped_pq_signature_is_scheme_downgrade():
    # unit test, stubbed verifier, not a proof result
    def m(rig, r, ups):
        env, d, rc = ATTACKS["forged"]["builder"](rig.s, r, 1, ups[1].delta, stripped=True)
        ups[1] = Update(1, env, d, rec(1))
        return ups
    rig, fins = _attack_round(m)
    _assert_dropped(rig, fins, 1, "scheme_downgrade")


def test_replayed_envelope_from_earlier_round_is_wrong_round():
    # unit test, stubbed verifier, not a proof result
    rig = Rig()
    old = {}

    def r0(r):
        ups = rig.honest_updates(r)
        old["u"] = ups[3]
        return ups

    def r1(r):
        ups = rig.honest_updates(r, only=[0, 1, 2, 4])
        env, d, rc = ATTACKS["replay"]["builder"](rig.s, r, 3, old["u"].delta, env=old["u"].envelope)
        return ups + [Update(3, env, d, old["u"].proof)]
    fins = rig.play([r0, r1])
    assert all(f is not None for fin in fins for f in fin)
    for n in rig.nodes:
        assert n.drop_log() == [(1, 3, "wrong_round")]
        assert n.accepted_ids(1) == [0, 1, 2, 4]


def test_replayed_envelope_same_round_is_replayed_nonce():
    # unit test, stubbed verifier, not a proof result
    def m(rig, r, ups):
        return ups + [Update(0, ups[0].envelope, ups[0].delta, ups[0].proof)]    # verbatim resend after admission
    rig = Rig()
    fins = one_round(rig, m)
    for n in rig.nodes:
        assert n.drop_log() == [(0, 0, "replayed_nonce")]
        assert n.accepted_ids(0) == list(range(N_CLIENTS))                       # original still counted once
    assert all(f is not None for f in fins[0])


def test_proof_swapped_from_another_client_is_journal_mismatch():
    # unit test, stubbed verifier, not a proof result
    def m(rig, r, ups):
        env, d, rc = ATTACKS["swap"]["builder"](rig.s, r, 1, ups[1].delta, receipt_a=rec(0))
        ups[1] = Update(1, env, d, rc)
        return ups
    rig, fins = _attack_round(m)
    _assert_dropped(rig, fins, 1, "bad_proof:journal_mismatch")


def test_proof_swapped_without_matching_hash_is_hash_mismatch():
    # unit test, stubbed verifier, not a proof result
    def m(rig, r, ups):
        env, d, rc = ATTACKS["swap"]["builder"](rig.s, r, 1, ups[1].delta, receipt_a=rec(0), hash_matches=False)
        ups[1] = Update(1, env, d, rc)
        return ups
    rig, fins = _attack_round(m)
    _assert_dropped(rig, fins, 1, "bad_proof:hash_mismatch")


# ---------------- faults ----------------
def test_one_silent_node_still_finalizes():
    # unit test, stubbed verifier, not a proof result
    rig = Rig({3: fault.SILENT})
    fins = one_round(rig, rounds=2)
    assert all(f is not None for fin in fins for f in fin)
    assert len({f[0] for fin in fins[:1] for f in fin}) == 1


def test_one_equivocating_node_is_outvoted_honest_hash_wins():
    # unit test, stubbed verifier, not a proof result
    clean = one_round(Rig(), rounds=2)
    rig = Rig({3: fault.EQUIVOCATE})
    fins = one_round(rig, rounds=2)
    for fin, ref in zip(fins, clean):
        assert all(f is not None and f[0] == ref[0][0] for f in fin)             # honest hash, not the bad one
    votes = rig.honest[0].votes_by_hash(1)
    assert sorted(votes.values()) == [1, 3]                                      # 3 honest vs the lone bad vote


@pytest.mark.parametrize("faults", [{2: fault.SILENT, 3: fault.SILENT},
                                    {2: fault.SILENT, 3: fault.EQUIVOCATE},
                                    {2: fault.EQUIVOCATE, 3: fault.EQUIVOCATE}])
def test_two_faulty_nodes_do_not_finalize(faults):
    # unit test, stubbed verifier, not a proof result
    rig = Rig(faults)
    fins = one_round(rig)
    assert all(f is None for f in fins[0])


# ---------------- one real Phase 3 receipt (verify only) ----------------
def test_real_phase3_receipt_through_zk_check():
    """Real receipt r0_c0 + real `qs-zk verify` via zk_check (verify only; no prover, no dev mode)."""
    from fl import client, data, merkle, model
    from fl.simulate import load_cfg
    from zk.bridge import cli
    receipt_path = ZKDIR / "r0_c0.receipt"
    if not receipt_path.exists():
        pytest.skip(f"no Phase 3 receipt at {receipt_path}")
    if not cli.binary().exists():
        pytest.skip(f"qs-zk binary missing at {cli.binary()}; build zk/ to run")
    cfg = {**load_cfg("configs/mvp.yaml"), **load_cfg("configs/phase3.yaml")}
    cfg.pop("base", None)
    seed = int(cfg["seeds"][0])
    K, batch = cfg["fl"]["K"], cfg["fl"]["batch"]
    lr_fx, b2 = int(fx.to_fx(cfg["fl"]["lr"])), fx.bound_sq(cfg["norm_bound_B"])
    clients, _ = data.load(seed, cfg["clients"])
    w = model.init(seed).astype(np.int64)
    trees = [merkle.MerkleTree(c.X, c.y) for c in clients]
    pol = zkpolicy.ZkPolicy(cli.verify_receipt, [len(c) for c in clients], K, batch, seed, lr_fx, b2)
    s = Session("hybrid", "ML-DSA-65", "Ed25519", cfg["clients"], cfg["aggregators"], seed,
                cfg.get("epoch_rounds", 5), [t.root for t in trees], zk=pol)
    s.begin_round(0, w)
    d = cli.client_blob(w, clients[0], 0, 0, seed, K, batch, lr_fx, b2, ev.make_nonce(seed, 0, 0), trees[0])[1]
    receipt = receipt_path.read_bytes()
    env = s.client_envelope(0, 0, d, receipt)
    check = zk_check(s.verifier)
    assert check(Update(0, env, d, receipt)) == (True, "ok")
