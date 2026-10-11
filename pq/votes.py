"""Aggregator vote message (domain tag "QSFL-vote-v1"). Phase 2 only signs and verifies votes;
nothing counts them yet (consensus is a later phase).

vote = (round, aggregator id, H(W_{t+1}), hash of the accepted-client set, nonce)
"""
import hashlib

from . import envelope as ev


def accepted_set_hash(client_ids):
    return hashlib.sha256(b"QSFL-set" + b"".join(int(c).to_bytes(4, "little") for c in sorted(client_ids))).digest()


def sign_vote(registry, algs, rnd, agg_id, h_next, accepted_ids, seed=0):
    nonce = ev.make_nonce(seed, rnd, agg_id, ev.KIND_VOTE)
    payload = ev.pack_vote(rnd, agg_id, h_next, accepted_set_hash(accepted_ids), nonce)
    return ev.sign_payload(registry, "agg", agg_id, algs, payload)
