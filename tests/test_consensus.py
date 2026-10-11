"""Consensus-lite: 4 aggregators, f=1. Small synthetic model, Ed25519 only (no prover, light)."""
import asyncio

import numpy as np
import pytest

from consensus import fault
from consensus.messages import Update, sign_propose, verify_propose
from consensus.node import Node, Network, run_round, run_rounds_with
from pq import envelope as ev
from pq import policy
from pq import registry as rg

N, F, N_CLIENTS, DIM = 4, 1, 5, 16
ALG = "Ed25519"


def build(faults=None, defence="fedavg", mode="classical"):
    reg = rg.KeyRegistry(N_CLIENTS, N, [ALG], seed=1, epoch_rounds=100)
    net = Network(N)
    nodes = []
    for i in range(N):
        v = policy.Verifier(reg, mode, classical_alg=ALG)
        nodes.append(Node(i, N, F, reg, v, net, defence=defence, B2=None,
                          fault_mode=(faults or {}).get(i, fault.HONEST), seed=1))
    return reg, net, nodes


def updates(reg, rnd, w, algs, deltas):
    h_w = ev.model_hash(w)
    out = []
    for c, d in enumerate(deltas):
        env = ev.sign_update(reg, algs, rnd, c, h_w, d, b"\x00" * 32, ev.make_nonce(1, rnd, c))
        out.append(Update(c, env, d))
    return out


def run(faults=None, rounds=2, tamper=None):
    reg, net, nodes = build(faults)
    algs = nodes[0].verifier.required
    rng = np.random.default_rng(0)
    w = np.zeros(DIM, dtype=np.int64)
    ws = []

    async def body():
        nonlocal w
        for r in range(rounds):
            deltas = [rng.integers(-5, 5, DIM).astype(np.int64) for _ in range(N_CLIENTS)]
            ups = updates(reg, r, w, algs, deltas)
            if tamper:
                tamper(ups)
            await run_round(nodes, net, reg, algs, r, w, ups)
            honest = [n for n in nodes if n.fault == fault.HONEST]
            fin = [n.finalized.get(r) for n in honest]
            ws.append(fin)
            if fin[0]:
                w = fin[0][1]

    asyncio.run(run_rounds_with(nodes, net, body))
    return nodes, ws


def test_benign_finalizes_every_round_at_every_node():
    nodes, ws = run(rounds=3)
    for fin in ws:
        assert all(f is not None for f in fin) and len({f[0] for f in fin}) == 1
    assert all(not n.rejects and not n.bad_votes for n in nodes)


def test_one_silent_node_still_finalizes():
    nodes, ws = run({3: fault.SILENT})
    assert all(f is not None for fin in ws for f in fin)           # 3 honest votes = 2f+1


def test_one_equivocating_node_is_outvoted():
    nodes, ws = run({3: fault.EQUIVOCATE})
    _, clean = run()
    for fin, ref in zip(ws, clean):
        assert all(f is not None and f[0] == ref[0][0] for f in fin)   # same hash as with no fault
    assert not any(n.equivocators for n in nodes)                  # it sent ONE (wrong) vote: outvoted, not double-voting


def test_two_faulty_nodes_do_not_finalize():
    for pair in ({2: fault.SILENT, 3: fault.SILENT}, {2: fault.SILENT, 3: fault.EQUIVOCATE},
                 {2: fault.EQUIVOCATE, 3: fault.EQUIVOCATE}):
        nodes, ws = run(pair, rounds=1)
        assert all(f is None for f in ws[0])                       # f+1 faults break the 2f+1 quorum


def test_invalid_update_dropped_with_reason_and_round_still_finalizes():
    def tamper(ups):
        ups[0].delta = ups[0].delta * 50                           # delta no longer matches its commitment
    nodes, ws = run(tamper=tamper, rounds=1)
    assert all(f is not None for f in ws[0])
    assert all(n.rejects == [(0, 0, "commitment_mismatch")] for n in nodes)


def test_double_voting_node_is_flagged():
    reg, net, nodes = build()
    algs = nodes[0].verifier.required
    w = np.zeros(DIM, dtype=np.int64)
    from consensus.messages import Vote
    from pq import votes as pqv

    async def body():
        await run_round(nodes, net, reg, algs, 0, w, [])
        a = pqv.sign_vote(reg, algs, 0, 3, ev.model_hash(w + 1), [], seed=2)   # fresh nonce, other hash
        net.send(0, Vote(0, 3, a))
        await net.queues[0].join()
    asyncio.run(run_rounds_with(nodes, net, body))
    assert (0, 3) in nodes[0].equivocators


def test_propose_signature_and_round_checks():
    reg = rg.KeyRegistry(1, N, [ALG], seed=1)
    w = np.arange(DIM, dtype=np.int64)
    p = sign_propose(reg, [ALG], 0, 0, w)
    assert verify_propose(reg, [ALG], p, 0) == (True, "ok")
    assert verify_propose(reg, [ALG], p, 1) == (False, "wrong_round")
    p.w = w + 1                                                    # model swapped after signing
    assert verify_propose(reg, [ALG], p, 0) == (False, "bad_signature")
    p.sigs = []
    assert verify_propose(reg, [ALG], p, 0) == (False, "unsigned")


# ---- zk_check (stubbed receipt verifier) ----
from consensus.node import zk_check
from pq.zkpolicy import ZkPolicy

GOOD = b"stub-receipt-ok"


def _stub_verify(receipt, expected_public):
    return (True, "ok") if receipt.startswith(b"stub-receipt") else (False, "journal_mismatch")


def _zk_build():
    reg = rg.KeyRegistry(N_CLIENTS, N, [ALG], seed=1, epoch_rounds=100)
    net = Network(N)
    zk = ZkPolicy(_stub_verify, n_c=[10] * N_CLIENTS, K=1, batch=1, seed=1, lr_fx=1, B2=1)
    nodes = []
    for i in range(N):
        v = policy.Verifier(reg, "classical", classical_alg=ALG, zk=zk)
        nodes.append(Node(i, N, F, reg, v, net, verify_update=zk_check(v), seed=1))
    return reg, net, nodes


def _zk_run(mutate):
    reg, net, nodes = _zk_build()
    algs = nodes[0].verifier.required
    w = np.zeros(DIM, dtype=np.int64)
    h_w = ev.model_hash(w)
    ups = []
    for c in range(N_CLIENTS):
        d = np.full(DIM, c + 1, dtype=np.int64)
        env = ev.sign_update(reg, algs, 0, c, h_w, d, b"\x00" * 32, ev.make_nonce(1, 0, c),
                             proof_hash=ev.proof_hash(GOOD))
        ups.append(Update(c, env, d, GOOD))
    mutate(ups)

    async def body():
        await run_round(nodes, net, reg, algs, 0, w, ups)
    asyncio.run(run_rounds_with(nodes, net, body))
    return nodes


def test_zk_check_requires_zk_policy():
    # unit test, stubbed verifier, not a proof result
    reg = rg.KeyRegistry(1, N, [ALG], seed=1)
    with pytest.raises(ValueError):
        zk_check(policy.Verifier(reg, "classical", classical_alg=ALG))


def test_zk_valid_stub_receipt_admitted():
    # unit test, stubbed verifier, not a proof result
    nodes = _zk_run(lambda ups: None)
    for n in nodes:
        assert n.accepted_ids(0) == list(range(N_CLIENTS)) and n.drop_log() == []
        assert 0 in n.finalized
        assert list(n.votes_by_hash(0).values()) == [N]


def test_zk_missing_receipt_dropped():
    # unit test, stubbed verifier, not a proof result
    def m(ups):
        ups[2].proof = None
    for n in _zk_run(m):
        assert n.drop_log() == [(0, 2, "bad_proof:missing_receipt")]
        assert 2 not in n.accepted_ids(0)
        assert 0 in n.finalized


def test_zk_swapped_receipt_dropped():
    # unit test, stubbed verifier, not a proof result
    def m(ups):
        ups[1].proof = b"stub-receipt-from-another-client"
    for n in _zk_run(m):
        assert n.drop_log() == [(0, 1, "bad_proof:hash_mismatch")]   # SHA256 differs from signed proof_hash
        assert 1 not in n.accepted_ids(0)
