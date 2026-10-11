"""Consensus-lite aggregator node (simulated network: asyncio queues, no real sockets).

Per round a node: takes the leader's signed Propose -> verifies each Update through the pluggable
`verify_update` hook (PQ signature now, PQ + ZK once Phase 3 lands) -> keeps valid updates only
(rejects are logged with a reason) -> computes the robust aggregate and W_{t+1} -> signs a vote on
H(W_{t+1}) -> broadcasts it -> finalizes once it holds 2f+1 valid votes for the same hash.

Fixed leader, synchronous rounds (the driver sends Close once every update has been delivered).
Leader rotation / view change, partial synchrony and real networking are deferred (see the plan).
"""
import asyncio
import logging
from dataclasses import dataclass, field

import numpy as np

from fl import aggregate
from fl import fixedpoint as fx
from pq import envelope as ev
from pq import votes as pqvotes

from . import fault
from .messages import Propose, Update, Vote, sign_propose, verify_propose

log = logging.getLogger("quantumshield.consensus")


def signature_check(verifier):
    """Default verify_update hook: the Phase 2 signature/commitment path only."""
    def check(update):
        return verifier.verify_envelope(update.envelope, update.delta)
    return check


def zk_check(verifier):
    """verify_update hook for Phase 4: PQ signature + commitment + ZK receipt in one call.
    The verifier must have been built with a ZkPolicy. Reason codes pass through unchanged."""
    if getattr(verifier, "zk", None) is None:
        raise ValueError("zk_check needs a Verifier built with zk=ZkPolicy(...)")

    def check(update):
        return verifier.verify_envelope(update.envelope, update.delta, update.proof)
    return check


@dataclass
class Close:
    """Local control message (not on the wire): no more updates for `round`."""
    round: int


@dataclass
class Stop:
    pass


@dataclass
class _Round:
    w: np.ndarray
    h_w: bytes
    accepted: dict = field(default_factory=dict)       # client_id -> delta
    w_next: np.ndarray = None
    h_next: bytes = None
    voted: dict = field(default_factory=dict)          # agg_id -> h_next (first vote wins)
    finalized: bool = False


class Network:
    """Asyncio-queue 'network' between aggregators. Clients and the driver `send`/`broadcast` in."""

    def __init__(self, n_nodes):
        self.queues = [asyncio.Queue() for _ in range(n_nodes)]

    def send(self, to, msg):
        self.queues[to].put_nowait(msg)

    def broadcast(self, msg, exclude=None):
        for i, q in enumerate(self.queues):
            if i != exclude:
                q.put_nowait(msg)


class Node:
    def __init__(self, nid, n, f, registry, verifier, net, defence="fedavg", B2=None,
                 verify_update=None, fault_mode=fault.HONEST, seed=0):
        if n < 3 * f + 1:
            raise ValueError(f"need n >= 3f+1, got n={n}, f={f}")
        self.id, self.n, self.f, self.quorum = nid, n, f, 2 * f + 1
        self.registry, self.verifier, self.net = registry, verifier, net
        self.defence, self.B2, self.seed = defence, B2, seed
        self.verify_update = verify_update or signature_check(verifier)
        self.fault = fault.check(fault_mode)
        self.rounds = {}                # round -> _Round
        self.finalized = {}             # round -> (h_next, w_next)
        self.rejects = []               # (round, client_id, reason)
        self.equivocators = set()       # (round, agg_id) who sent two different votes
        self.bad_votes = []             # (round, agg_id, reason)

    # --- per-round records (demo) ---
    def drop_log(self):
        """[(round, client_id, reason)] for every dropped update, in arrival order."""
        return list(self.rejects)

    def accepted_ids(self, rnd):
        """Sorted client ids whose update was accepted in `rnd` ([] if unknown round)."""
        st = self.rounds.get(rnd)
        return sorted(st.accepted) if st else []

    def votes_by_hash(self, rnd):
        """{h_next: number of valid votes (incl. own)} for `rnd`."""
        st = self.rounds.get(rnd)
        out = {}
        for h in (st.voted.values() if st else ()):
            out[h] = out.get(h, 0) + 1
        return out

    # --- message loop ---
    async def run(self):
        q = self.net.queues[self.id]
        while True:
            msg = await q.get()
            try:
                if isinstance(msg, Stop):
                    return
                self.handle(msg)
            finally:
                q.task_done()

    def handle(self, msg):
        if isinstance(msg, Propose):
            self.on_propose(msg)
        elif isinstance(msg, Update):
            self.on_update(msg)
        elif isinstance(msg, Close):
            self.on_close(msg.round)
        elif isinstance(msg, Vote):
            self.on_vote(msg)

    # --- steps ---
    def on_propose(self, p):
        if p.round in self.rounds:                     # replayed / duplicate Propose must not reset state
            log.warning("node %d ignored duplicate propose: round=%d", self.id, p.round)
            return
        ok, reason = verify_propose(self.registry, self.verifier.required, p, p.round)
        if not ok:
            log.warning("node %d rejected propose: round=%d reason=%s", self.id, p.round, reason)
            return
        self.registry.advance_to_round(p.round)
        self.verifier.begin_round(p.round, p.h_w)
        self.rounds[p.round] = _Round(p.w, p.h_w)

    def on_update(self, u):
        rnd = self.verifier.round
        st = self.rounds.get(rnd)
        if st is None:
            self.rejects.append((rnd, u.client_id, "no_proposal"))
            return
        ok, reason = self.verify_update(u)
        if ok:
            st.accepted[u.client_id] = u.delta
        else:
            self.rejects.append((rnd, u.client_id, reason))
            log.warning("node %d dropped update: round=%d client=%d reason=%s", self.id, rnd, u.client_id, reason)

    def on_close(self, rnd):
        st = self.rounds.get(rnd)
        if st is None or st.w_next is not None:
            return
        ids = sorted(st.accepted)                      # same order at every node => same W_{t+1}
        if ids:
            agg = aggregate.DEFENCES[self.defence]([st.accepted[c] for c in ids], self.B2)
            st.w_next = fx.check(st.w + agg)
        else:
            st.w_next = st.w
        st.h_next = ev.model_hash(st.w_next)
        voted_model = fault.vote_model(self.fault, st.w_next)
        if voted_model is not None:
            env = pqvotes.sign_vote(self.registry, self.verifier.required, rnd, self.id,
                                    ev.model_hash(voted_model), ids, self.seed)
            vote = Vote(rnd, self.id, env)
            st.voted[self.id] = vote.h_next
            self.net.broadcast(vote, exclude=self.id)
        self._try_finalize(rnd)

    def on_vote(self, v):
        st = self.rounds.get(v.round)
        if st is None:
            self.bad_votes.append((v.round, v.agg_id, "no_proposal"))
            return
        ok, reason = self.verifier.verify_vote(v.envelope)
        if not ok:
            self.bad_votes.append((v.round, v.agg_id, reason))
            log.warning("node %d rejected vote: round=%d agg=%d reason=%s", self.id, v.round, v.agg_id, reason)
            return
        prev = st.voted.get(v.agg_id)
        if prev is None:
            st.voted[v.agg_id] = v.h_next
        elif prev != v.h_next:
            self.equivocators.add((v.round, v.agg_id))
            log.warning("node %d: aggregator %d equivocated in round %d", self.id, v.agg_id, v.round)
        self._try_finalize(v.round)

    def _try_finalize(self, rnd):
        st = self.rounds[rnd]
        if st.finalized or st.h_next is None:
            return
        support = sum(1 for h in st.voted.values() if h == st.h_next)
        if support >= self.quorum:
            st.finalized = True
            self.finalized[rnd] = (st.h_next, st.w_next)


async def run_round(nodes, net, registry, algs, rnd, w, client_updates, leader_id=0):
    """Drive one synchronous round and wait until every queue is drained.
    `client_updates`: list of Update broadcast to every aggregator (a client may send
    different updates to different aggregators: pass a dict {node_id: [Update, ...]} instead)."""
    registry.advance_to_round(rnd)
    net.broadcast(sign_propose(registry, algs, rnd, leader_id, w))
    for i in range(len(nodes)):
        ups = client_updates[i] if isinstance(client_updates, dict) else client_updates
        for u in ups:
            net.send(i, u)
    net.broadcast(Close(rnd))
    await asyncio.gather(*(q.join() for q in net.queues))


async def run_rounds_with(nodes, net, body):
    """Start node tasks, run `await body()`, then stop them cleanly."""
    tasks = [asyncio.create_task(n.run()) for n in nodes]
    try:
        return await body()
    finally:
        net.broadcast(Stop())
        await asyncio.gather(*tasks)
