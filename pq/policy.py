"""Aggregator-side verification: the only path by which a signed update or vote is admitted.

Modes (config `signatures`): none | classical (Ed25519) | pq (configured ML-DSA/Falcon/SLH-DSA)
| hybrid (Ed25519 AND the PQ scheme; both must verify). An envelope must carry exactly the
signatures the mode requires, so stripping the PQ signature from a hybrid envelope is rejected
as `scheme_downgrade`.

Check order (cheap before expensive; nothing is remembered until every check has passed, so a
forger cannot burn a victim's nonce):
    kind/parse -> signature set -> key (identity, revoked, stale epoch) -> round -> H(W_t)
    -> signature(s) -> commitment C_i vs received delta -> [ZK proof, if enabled] -> nonce / duplicate submission.
"""
from . import envelope as ev
from . import registry as rg
from . import sig

MODES = ("none", "classical", "pq", "hybrid")


class Verifier:
    def __init__(self, registry, mode, pq_alg="ML-DSA-65", classical_alg="Ed25519", zk=None):
        if mode not in MODES:
            raise ValueError(f"signatures must be one of {MODES}, got {mode!r}")
        self.registry, self.mode = registry, mode
        self.required = {"none": [], "classical": [classical_alg], "pq": [pq_alg],
                         "hybrid": [classical_alg, pq_alg]}[mode]
        if zk is not None and mode == "none":
            raise ValueError("a ZkPolicy needs signatures != none: mode 'none' admits updates without checks")
        self.zk = zk          # optional pq.zkpolicy.ZkPolicy: when set, every update needs a valid v2 proof
        self.round, self.h_w = None, None
        self._nonces, self._submitted = set(), set()

    def begin_round(self, rnd, h_w):
        self.round, self.h_w = rnd, h_w

    # --- shared pieces ---
    def _check_keys(self, env, role, ident):
        if not env.sigs:
            return "unsigned"
        algs = [a for a, _, _ in env.sigs]
        if sorted(algs) != sorted(self.required):
            return "scheme_downgrade"
        for alg, kid, _ in env.sigs:
            parsed = rg.parse_key_id(kid)
            if parsed is None or parsed[:2] != (role, ident) or parsed[3] != alg:
                return "unknown_key" if parsed is None else "key_identity_mismatch"
            st = self.registry.status(kid)
            if st != "ok":
                return f"{st}_key"
        return None

    def _check_sigs(self, env, kind):
        for alg, kid, s in env.sigs:
            if not sig.verify(alg, self.registry.public_key(kid), ev.signed_bytes(kind, alg, env.payload), s):
                return "bad_signature"
        return None

    # --- updates ---
    def verify_envelope(self, env, delta, receipt=None):
        """-> (accepted, reason). `delta` is the update as received (int64 vector). `receipt` is the
        proof file bytes; required when the verifier was built with a ZkPolicy."""
        if self.mode == "none":
            return True, "signatures_disabled"
        if ev.payload_kind(env.payload) != ev.KIND_UPDATE:
            return False, "wrong_kind"
        p = ev.parse_update(env.payload)
        if p is None:
            return False, "malformed"
        bad = self._check_keys(env, "client", p["client_id"])
        if bad:
            return False, bad
        if p["round"] != self.round:
            return False, "wrong_round"
        if p["h_w"] != self.h_w:
            return False, "wrong_model_hash"
        bad = self._check_sigs(env, ev.KIND_UPDATE)
        if bad:
            return False, bad
        if ev.commit(delta, p["nonce"]) != p["c"]:
            return False, "commitment_mismatch"
        # cheap replay checks before the expensive proof verification (no state is written yet)
        if (p["client_id"], p["nonce"]) in self._nonces:
            return False, "replayed_nonce"
        if (p["client_id"], p["round"]) in self._submitted:
            return False, "duplicate_submission"
        if self.zk is not None:
            ok, why = self.zk.check(p, receipt)
            if not ok:
                return False, why
        self._nonces.add((p["client_id"], p["nonce"]))
        self._submitted.add((p["client_id"], p["round"]))
        return True, "ok"

    # --- votes (signing and verifying only; no consensus yet) ---
    def verify_vote(self, env):
        if self.mode == "none":
            return True, "signatures_disabled"
        if ev.payload_kind(env.payload) != ev.KIND_VOTE:
            return False, "wrong_kind"
        p = ev.parse_vote(env.payload)
        if p is None:
            return False, "malformed"
        bad = self._check_keys(env, "agg", p["agg_id"])
        if bad:
            return False, bad
        if p["round"] != self.round:
            return False, "wrong_round"
        bad = self._check_sigs(env, ev.KIND_VOTE)
        if bad:
            return False, bad
        if (p["agg_id"], p["nonce"]) in self._nonces:
            return False, "replayed_nonce"
        self._nonces.add((p["agg_id"], p["nonce"]))
        return True, "ok"
