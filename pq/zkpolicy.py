"""Aggregator-side proof check for envelope v2 (docs/zk_interface.md section 8).

Order: envelope carries proof_hash -> SHA256(receipt) matches -> journal built from the signed
envelope fields and run configuration equals the receipt journal -> receipt verifies against the
guest image ID. `verify_receipt(receipt_bytes, expected_public) -> (ok, reason)` is supplied by the
bridge (zk/bridge), which calls the real qs-zk CLI; this module never proves or fakes anything.
"""
import struct

from . import envelope as ev

JOURNAL_LEN = 146


def expected_public(relation, t, c, n_c, K, batch, seed, lr_fx, B2, h_w, commitment, root):
    """The 146-byte journal of docs/zk_interface.md section 3."""
    if relation == 2:
        K = batch = 0
    return (b"QSZK" + bytes([1, relation]) + struct.pack("<IIIII", t, c, n_c, K, batch)
            + struct.pack("<QqQ", seed, lr_fx, B2) + h_w + commitment + root)


class ZkPolicy:
    def __init__(self, verify_receipt, n_c, K, batch, seed, lr_fx, B2, relation=1, roots=None, allow_cut=False):
        """n_c: list of dataset sizes by client id (trusted configuration, statement section 5)."""
        if relation != 1 and not allow_cut:
            raise ValueError("only the full relation (1) is accepted; relation 2 is the cut-ladder fallback (allow_cut=True)")
        self.verify_receipt, self.n_c = verify_receipt, n_c
        self.roots = roots            # optional registered Merkle roots by client id (R is otherwise client-chosen)
        self.params = dict(relation=relation, K=K, batch=batch, seed=seed, lr_fx=lr_fx, B2=B2)

    def check(self, p, receipt):
        """p = parsed update payload. -> (ok, reason)."""
        if p.get("proof_hash") is None:
            return False, "bad_proof:missing_proof_hash"
        if receipt is None:
            return False, "bad_proof:missing_receipt"
        if ev.proof_hash(receipt) != p["proof_hash"]:
            return False, "bad_proof:hash_mismatch"
        cid = p["client_id"]
        if not 0 <= cid < len(self.n_c):
            return False, "bad_proof:unknown_client"
        if self.roots is not None and p["r"] != self.roots[cid]:
            return False, "bad_proof:unregistered_root"
        exp = expected_public(t=p["round"], c=cid, n_c=self.n_c[cid], h_w=p["h_w"],
                              commitment=p["c"], root=p["r"], **self.params)
        ok, why = self.verify_receipt(receipt, exp)
        return (True, "ok") if ok else (False, f"bad_proof:{why}")
