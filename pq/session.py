"""Glue between the FL loop and the signature layer: key registry + verifier + client signing,
aggregator vote signing. One Session per FL run. Used only when `signatures != none`."""
import logging
from collections import Counter

from fl import merkle

from . import envelope as ev
from . import policy, votes
from . import registry as rg

log = logging.getLogger("quantumshield.aggregator")


def merkle_roots(clients):
    """R_i for each client: fl/merkle.py root over its (x, y) samples (static, computed once)."""
    return [merkle.MerkleTree(ds.X, ds.y).root for ds in clients]


class Session:
    def __init__(self, mode, pq_alg, classical_alg, n_clients, n_aggs, seed, epoch_rounds, roots, zk=None):
        self.mode, self.seed, self.roots, self.n_aggs = mode, seed, roots, n_aggs
        # every identity gets both an Ed25519 and a PQ key, whatever the mode, so hybrid/downgrade
        # scenarios and the forgery simulation can be expressed against one registry.
        self.registry = rg.KeyRegistry(n_clients, n_aggs, [classical_alg, pq_alg], seed, epoch_rounds)
        self.verifier = policy.Verifier(self.registry, mode, pq_alg, classical_alg, zk=zk)
        self.algs = self.verifier.required
        self.round, self.h_w = None, None
        self.dropped = Counter()      # reason -> count
        self.drop_log = []            # (round, client, reason)
        self.wire_bytes = 0
        self.votes_ok = self.votes_bad = 0

    def begin_round(self, t, w):
        self.registry.advance_to_round(t)
        self.round, self.h_w = t, ev.model_hash(w)
        self.verifier.begin_round(t, self.h_w)

    def nonce(self, t, c):
        return ev.make_nonce(self.seed, t, c)

    def client_envelope(self, t, c, d, receipt=None):
        """`receipt` (proof file bytes) makes it a v2 envelope carrying proof_hash."""
        ph = None if receipt is None else ev.proof_hash(receipt)
        env = ev.sign_update(self.registry, self.algs, t, c, self.h_w, d, self.roots[c], self.nonce(t, c), ph)
        self.wire_bytes += len(env.wire())
        return env

    def admit(self, t, c, env, d, receipt=None):
        """Aggregator-side gate: True iff the update may enter aggregation."""
        ok, reason = self.verifier.verify_envelope(env, d, receipt)
        if not ok:
            self.dropped[reason] += 1
            self.drop_log.append((t, c, reason))
            log.warning("dropped update: round=%d client=%d reason=%s", t, c, reason)
        return ok

    def cast_votes(self, t, w_next, accepted_ids):
        """Every aggregator signs a vote on (H(W_{t+1}), accepted set); every vote is verified."""
        h_next = ev.model_hash(w_next)
        for a in range(self.n_aggs):
            env = votes.sign_vote(self.registry, self.algs, t, a, h_next, accepted_ids, self.seed)
            self.wire_bytes += len(env.wire())
            ok, reason = self.verifier.verify_vote(env)
            if ok:
                self.votes_ok += 1
            else:
                self.votes_bad += 1
                log.warning("rejected vote: round=%d aggregator=%d reason=%s", t, a, reason)
