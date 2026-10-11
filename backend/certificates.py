"""Certificates: a certificate is a round's signed votes (docs/ui_issues.md UI-002). Verification uses a
secret-free registry (KeyRegistry.from_snapshot, public keys only) and Verifier.verify_vote per vote.
No secret key is read anywhere in this module."""
import copy
import hashlib

from pq import envelope as ev
from pq import policy
from pq import registry as rg

SOURCE = "pq/policy.py Verifier.verify_vote"


def vote_to_dict(vote):
    env = vote.envelope
    return {"node": int(vote.agg_id), "payload": env.payload.hex(),
            "sigs": [{"alg": a, "key_id": k, "sig": s.hex()} for a, k, s in env.sigs]}


def vote_set_id(votes):
    """sha256 prefix (12 hex) of the canonical vote set: votes sorted by node, fields concatenated."""
    h = hashlib.sha256()
    for v in sorted(votes, key=lambda v: v["node"]):
        h.update(int(v["node"]).to_bytes(4, "little"))
        h.update(bytes.fromhex(v["payload"]))
        for s in v["sigs"]:
            h.update(s["alg"].encode() + b"|" + s["key_id"].encode() + b"|" + bytes.fromhex(s["sig"]))
    return h.hexdigest()[:12]


def _envelope(v):
    return ev.Envelope(bytes.fromhex(v["payload"]),
                       [(s["alg"], s["key_id"], bytes.fromhex(s["sig"])) for s in v["sigs"]])


def verify(cert, snapshot, mode, pq_alg, classical_alg, f):
    """cert: {round, votes:[{node, payload, sigs}]}. snapshot: the run's public registry snapshot.
    -> response dict of POST /api/certificates/verify."""
    rnd = int(cert["round"])
    snap = copy.deepcopy(snapshot)
    snap["epoch"] = rnd // snap["epoch_rounds"]       # key status 'ok' is relative to the round's epoch
    reg = rg.KeyRegistry.from_snapshot(snap)          # public keys only: _sk is empty
    ver = policy.Verifier(reg, mode, pq_alg, classical_alg)
    ver.begin_round(rnd, b"")
    checked, ok_by_hash = [], {}
    for v in cert["votes"]:
        node = v.get("node")
        try:
            env = _envelope(v)
            p = ev.parse_vote(env.payload)
            if p is None:
                ok, why = False, "malformed"
            elif p["agg_id"] != node:
                ok, why = False, "node_mismatch"
            else:
                ok, why = ver.verify_vote(env)
        except (ValueError, KeyError, TypeError):
            p, ok, why = None, False, "malformed"
        checked.append({"node": node, "ok": bool(ok), "reason": why})
        if ok:
            ok_by_hash.setdefault(p["h_next"], set()).add(p["agg_id"])
    quorum = 2 * f + 1
    quorum_met = any(len(s) >= quorum for s in ok_by_hash.values())
    return {"valid": bool(quorum_met and all(c["ok"] for c in checked)), "quorum_met": quorum_met,
            "checked": checked, "public_keys_only": True, "source": SOURCE}
