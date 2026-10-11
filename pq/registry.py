"""Simulated PKI: per-client and per-aggregator keys, per-epoch rotation, revocation list.

In memory, with a JSON snapshot of PUBLIC state only (public keys, epoch, revocations). A registry
built with KeyRegistry(...) also holds the secret keys, standing in for each node's own key store;
KeyRegistry.load() returns a verifier-side view with no secrets.

Key id = "<role>:<id>:<epoch>:<alg>", e.g. "client:3:0:ML-DSA-65".
"""
import json
from pathlib import Path

from . import sig

ROLES = ("client", "agg")


def make_key_id(role, ident, epoch, alg):
    return f"{role}:{ident}:{epoch}:{alg}"


def parse_key_id(kid):
    """-> (role, ident, epoch, alg) or None if malformed."""
    try:
        role, ident, epoch, alg = kid.split(":")
        if role not in ROLES or alg not in sig.SCHEMES:
            return None
        return role, int(ident), int(epoch), alg
    except (ValueError, AttributeError):
        return None


class KeyRegistry:
    def __init__(self, n_clients, n_aggregators, algs, seed=0, epoch_rounds=5):
        self.n = {"client": n_clients, "agg": n_aggregators}
        self.algs = list(dict.fromkeys(algs))
        self.seed = int(seed)
        self.epoch_rounds = int(epoch_rounds)
        self.epoch = -1
        self.pks = {}          # key_id -> public key bytes (all epochs, so stale keys are recognised)
        self.revoked = set()   # key_ids
        self._sk = {}          # key_id -> secret key (simulated per-node key stores; not snapshotted)
        self.rotate()

    # --- lifecycle ---
    def rotate(self):
        """Start the next epoch: fresh keys for every identity and algorithm. Old keys become stale."""
        self.epoch += 1
        sig.seed_rng(b"QSFL-keys" + self.seed.to_bytes(8, "little") + self.epoch.to_bytes(4, "little"))
        for role in ROLES:
            for i in range(self.n[role]):
                for alg in self.algs:
                    pk, sk = sig.keygen(alg)
                    kid = make_key_id(role, i, self.epoch, alg)
                    self.pks[kid], self._sk[kid] = pk, sk

    def epoch_for_round(self, rnd):
        return rnd // self.epoch_rounds

    def advance_to_round(self, rnd):
        while self.epoch < self.epoch_for_round(rnd):
            self.rotate()

    def revoke(self, key_id):
        self.revoked.add(key_id)

    # --- lookups ---
    def key_id(self, role, ident, alg):
        """Current-epoch key id."""
        return make_key_id(role, ident, self.epoch, alg)

    def status(self, key_id):
        """'unknown' | 'revoked' | 'stale' | 'ok'."""
        if key_id not in self.pks:
            return "unknown"
        if key_id in self.revoked:
            return "revoked"
        if parse_key_id(key_id)[2] != self.epoch:
            return "stale"
        return "ok"

    def public_key(self, key_id):
        return self.pks.get(key_id)

    def secret_key(self, role, ident, alg, epoch=None):
        """The node's own secret key (simulation only)."""
        return self._sk[make_key_id(role, ident, self.epoch if epoch is None else epoch, alg)]

    # --- snapshot (public data only) ---
    def snapshot(self):
        return {"n": self.n, "algs": self.algs, "seed": self.seed, "epoch_rounds": self.epoch_rounds,
                "epoch": self.epoch, "revoked": sorted(self.revoked),
                "pks": {k: v.hex() for k, v in sorted(self.pks.items())}}

    def save(self, path):
        Path(path).write_text(json.dumps(self.snapshot(), indent=1))

    @classmethod
    def from_snapshot(cls, snap):
        r = cls.__new__(cls)
        r.n, r.algs, r.seed = snap["n"], snap["algs"], snap["seed"]
        r.epoch_rounds, r.epoch = snap["epoch_rounds"], snap["epoch"]
        r.revoked = set(snap["revoked"])
        r.pks = {k: bytes.fromhex(v) for k, v in snap["pks"].items()}
        r._sk = {}
        return r

    @classmethod
    def load(cls, path):
        return cls.from_snapshot(json.loads(Path(path).read_text()))
