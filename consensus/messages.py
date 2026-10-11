"""Consensus-lite message types: Propose, Update, Vote. All are signed.

Update and Vote wrap the Phase 2 signed `pq.envelope.Envelope` unchanged (so they keep their own
domain tags and verification path). Propose is the only message defined here: the leader's
broadcast of (round, H(W_t), W_t), signed over its own domain tag "QSFL-propose-v1".
"""
import struct
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from pq import envelope as ev
from pq import registry as rg
from pq import sig

PROPOSE_TAG = b"QSFL-propose-v1"


def _propose_bytes(alg, rnd, leader_id, h_w):
    a = alg.encode()
    return PROPOSE_TAG + bytes([len(a)]) + a + struct.pack("<II", rnd, leader_id) + h_w


@dataclass
class Propose:
    round: int
    leader_id: int
    w: np.ndarray                                  # W_t, int64
    sigs: list = field(default_factory=list)       # [(alg, key_id, signature)]

    @property
    def h_w(self):
        return ev.model_hash(self.w)


@dataclass
class Update:
    """A client's submission to one aggregator: signed envelope + the Δ it commits to.
    `proof` is the ZK receipt (None until Phase 3 is wired in)."""
    client_id: int
    envelope: ev.Envelope
    delta: np.ndarray
    proof: Optional[bytes] = None


@dataclass
class Vote:
    """An aggregator's signed vote on H(W_{t+1}). `envelope` is the Phase 2 vote envelope."""
    round: int
    agg_id: int
    envelope: ev.Envelope

    @property
    def h_next(self):
        return ev.parse_vote(self.envelope.payload)["h_next"]


def sign_propose(registry, algs, rnd, leader_id, w):
    p = Propose(rnd, leader_id, np.asarray(w, dtype=np.int64))
    for alg in algs:
        sk = registry.secret_key("agg", leader_id, alg)
        s = sig.sign(alg, sk, _propose_bytes(alg, rnd, leader_id, p.h_w))
        p.sigs.append((alg, registry.key_id("agg", leader_id, alg), s))
    return p


def verify_propose(registry, required_algs, p, expected_round):
    """-> (ok, reason). Checks the signature set, key status, round and signatures."""
    if sorted(a for a, _, _ in p.sigs) != sorted(required_algs):
        return False, "scheme_downgrade" if p.sigs else "unsigned"
    if p.round != expected_round:
        return False, "wrong_round"
    for alg, kid, s in p.sigs:
        parsed = rg.parse_key_id(kid)
        if parsed is None or parsed[:2] != ("agg", p.leader_id) or parsed[3] != alg:
            return False, "key_identity_mismatch"
        st = registry.status(kid)
        if st != "ok":
            return False, f"{st}_key"
        if not sig.verify(alg, registry.public_key(kid), _propose_bytes(alg, p.round, p.leader_id, p.h_w), s):
            return False, "bad_signature"
    return True, "ok"
