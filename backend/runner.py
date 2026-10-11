"""Live scenario runner. Mirrors demo/run_demo.py:run_scenario (same calls into fl / pq / consensus / attacks, same
order, no changed logic) with four differences that cannot be had by calling run_scenario, which hardcodes the
aggregator and exposes limited consensus data (demo/ is not editable from the backend):

  * the chosen aggregator is passed as Node(defence=...),
  * the network records the signed Vote messages (for the consensus view and certificates),
  * diverged rounds are accuracy None (never 0.0; the 0.0 is a stored-file convention, D-012),
  * SSE events carry Rejection records and consensus info.

Nothing here proves anything. A drift test (tests/backend/test_runner.py) compares fedavg accuracies with run_scenario.
"""
import asyncio
import time
from collections import Counter

import numpy as np

from attacks import envelope_attacks, poison
from consensus.messages import Update, Vote
from consensus.node import Network, Node, run_round, run_rounds_with, signature_check
from demo.run_demo import F, N_AGG, norm_gate
from fl import client, data, model
from fl import fixedpoint as fx
from pq import policy
from pq import session as pqsession

from . import certificates, reasons
from .common import d012_note

QUORUM = 2 * F + 1
LEADER = 0


class RecordingNetwork(Network):
    """Network that also keeps every broadcast Vote (each node broadcasts its own vote once per round)."""

    def __init__(self, n):
        super().__init__(n)
        self.votes = []

    def broadcast(self, msg, exclude=None):
        if isinstance(msg, Vote):
            self.votes.append(msg)
        super().broadcast(msg, exclude)


def _convention_note():
    return ("Diverged: the int64 fixed-point model left its range (D-012). No accuracy is reported for this round. "
            "D-012 text: " + d012_note()["text"])


def run_seed(cfg, attack, defence_on, aggregator, seed, emit=lambda ev: None):
    """One seed. Returns dict(acc=[float|None...], diverged_round, rejections=[...], consensus=state dict, ...)."""
    n_cl, mal = cfg["clients"], cfg["malicious_clients"]
    nb = n_cl - mal
    fl = cfg["fl"]
    clients, test = data.load(seed, n_cl)
    B2 = fx.bound_sq(cfg["norm_bound_B"])
    lr_fx = int(fx.to_fx(fl["lr"]))
    mode = "hybrid" if defence_on else "classical"
    pq_alg, cl_alg = cfg.get("sig_alg", "ML-DSA-65"), cfg.get("classical_alg", "Ed25519")
    sess = pqsession.Session(mode, pq_alg, cl_alg, n_cl, N_AGG, seed, cfg.get("epoch_rounds", 5),
                             pqsession.merkle_roots(clients))
    net = RecordingNetwork(N_AGG)
    nodes = []
    for i in range(N_AGG):
        v = policy.Verifier(sess.registry, mode, pq_alg, cl_alg)
        hook = norm_gate(v, B2) if defence_on else signature_check(v)
        nodes.append(Node(i, N_AGG, F, sess.registry, v, net, defence=aggregator, B2=B2, verify_update=hook, seed=seed))
    res = dict(acc=[model.accuracy(model.init(seed), test)], diverged_round=None, stopped_round=None,
               latency_ms=[], update_env_bytes=[], rejects=Counter(), accepted=[], finalized_rounds=0)
    cons_rounds = []
    w = model.init(seed)
    prev = {}
    rounds = cfg["rounds"]

    def consensus_round(t):
        st = nodes[0].rounds.get(t)
        vs = [certificates.vote_to_dict(v) for v in net.votes if v.round == t]
        view_votes = []
        for v in net.votes:
            if v.round != t:
                continue
            counted = st is not None and st.voted.get(v.agg_id) == v.h_next
            view_votes.append(dict(node=v.agg_id, signer_alg="+".join(a for a, _, _ in v.envelope.sigs),
                                   hash=v.h_next.hex(), valid=bool(counted)))
        return dict(round=t, model_hash=(st.h_next.hex() if st is not None and st.h_next is not None else None),
                    votes=sorted(view_votes, key=lambda x: x["node"]), finalized=t in nodes[0].finalized,
                    equivocators=sorted(a for (r, a) in nodes[0].equivocators if r == t),
                    bad_votes=sum(1 for (r, _, _) in nodes[0].bad_votes if r == t),
                    certificate_id=vote_set_id_or_none(vs), raw_votes=vs)

    def event(t, **kw):
        base = dict(type="round", seed=seed, round=t, accuracy=None, diverged=False, accepted=[], accepted_count=0,
                    rejected_count=0, rejections=[], latency_ms=None, model_hash=None,
                    consensus=dict(leader=LEADER, votes=0, quorum=QUORUM, finalized=False))
        base.update(kw)
        emit(base)

    async def body():
        nonlocal w
        for t in range(rounds):
            sess.begin_round(t, w)
            ups, sent = [], {}
            for c in range(n_cl):
                idx = client.sample_indices(seed, t, c, fl["K"], fl["batch"], len(clients[c]))
                try:
                    d = client.local_train(w, clients[c], idx, lr_fx)
                except fx.FixedPointOverflow:             # the poisoned global model is out of int64 range (D-012)
                    res["diverged_round"] = t
                    res["acc"] += [None] * (rounds + 1 - len(res["acc"]))
                    cons_rounds.append(consensus_round(t))
                    event(t, diverged=True)
                    return
                if c >= nb and attack == "scaled":
                    d = poison.scaled(d, cfg["attack"]["scale"])
                env = sess.client_envelope(t, c, d)
                sent[c] = (env, d)
                if c >= nb and attack == "replay" and c in prev:
                    env, d = prev[c]                      # old envelope resent verbatim
                if c == 0 and attack == "forged":         # victim 0's Ed25519 key only
                    env, d = envelope_attacks.forge_with_classical_key(sess, 0, t, poison.scaled(d, cfg["attack"]["scale"]))
                ups.append(Update(c, env, d))
                res["update_env_bytes"].append(len(env.wire()))
            prev.update(sent)
            t0 = time.perf_counter()
            await run_round(nodes, net, sess.registry, sess.algs, t, w, ups)
            res["latency_ms"].append((time.perf_counter() - t0) * 1000)
            fin = nodes[0].finalized.get(t)
            res["accepted"].append(nodes[0].accepted_ids(t))
            rej = [reasons.rejection(r, c, why) for (r, c, why) in nodes[0].drop_log() if r == t]
            st = nodes[0].rounds.get(t)
            support = 0
            if st is not None and st.h_next is not None:
                support = nodes[0].votes_by_hash(t).get(st.h_next, 0)
            cons_rounds.append(consensus_round(t))
            common = dict(accepted=res["accepted"][-1], accepted_count=len(res["accepted"][-1]),
                          rejected_count=len(rej), rejections=rej, latency_ms=res["latency_ms"][-1])
            if fin is None:
                if st is None or st.w_next is None:       # on_close hit int64 overflow at every node (D-012)
                    res["diverged_round"] = t
                    res["acc"] += [None] * (rounds + 1 - len(res["acc"]))
                    event(t, diverged=True, **common)
                else:                                     # computed a model but < 2f+1 matching votes
                    res["stopped_round"] = t
                    res["acc"] += [None] * (rounds + 1 - len(res["acc"]))
                    common["rejections"] = rej + [reasons.rejection(t, None, "not_in_quorum")]
                    event(t, model_hash=st.h_next.hex()[:16],
                          consensus=dict(leader=LEADER, votes=support, quorum=QUORUM, finalized=False), **common)
                return
            res["finalized_rounds"] += 1
            w = fin[1]
            res["acc"].append(model.accuracy(w, test))
            event(t, accuracy=res["acc"][-1], model_hash=fin[0].hex()[:16],
                  consensus=dict(leader=LEADER, votes=support, quorum=QUORUM, finalized=True), **common)

    try:
        asyncio.run(run_rounds_with(nodes, net, body))
    except fx.FixedPointOverflow:
        if res["diverged_round"] is None:
            raise
    for r, c, why in nodes[0].drop_log():
        res["rejects"][(r, c, why)] += 1
    res["consensus"] = dict(seed=seed, attack=attack, defence="on" if defence_on else "off", aggregator=aggregator,
                            mode=mode, pq_alg=pq_alg, classical_alg=cl_alg, n=N_AGG, f=F, quorum=QUORUM,
                            rounds=cons_rounds, registry=sess.registry.snapshot())
    return res


def vote_set_id_or_none(vs):
    return certificates.vote_set_id(vs) if vs else None


def seed_summary(seed, res):
    """-> seed_done event."""
    stopped = res["stopped_round"]
    final = None if res["diverged_round"] is not None or stopped is not None else res["acc"][-1]
    note = _convention_note() if res["diverged_round"] is not None else (
        f"Stopped at round {stopped}: no 2f+1 matching votes, so no model was finalized." if stopped is not None else None)
    return dict(type="seed_done", seed=seed, final_accuracy=final, diverged_round=res["diverged_round"],
                convention_note=note)


def mean_or_none(xs):
    return float(np.mean(xs)) if xs else None
