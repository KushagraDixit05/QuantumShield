"""Signed envelope: (payload, signatures, key ids) with domain separation.

Update payload v1 (fixed layout, 138 B; v2 has version=2 and a trailing proof_hash 32 B, 170 B):
    version u8 | kind u8 (=1) | round u32 | client_id u32 | H(W_t) 32 | C_i 32 | R_i 32 | nonce 32
Vote payload (106 B):
    version u8 | kind u8 (=2) | round u32 | aggregator_id u32 | H(W_{t+1}) 32 | accepted-set hash 32 | nonce 32

What a signature signs:  DOMAIN_TAG || len(alg) u8 || alg || payload
so a signature cannot be moved to another message kind (update vs vote) or another algorithm
label. C_i = SHA256("QSFL-upd" || delta_le || nonce) exactly as in docs/zk_statement.md; H(W_t) is
SHA256 of the int64 little-endian model; R_i is the fl/merkle.py root over the client's samples.
"""
import hashlib
import struct
from dataclasses import dataclass, field

import numpy as np

from . import sig

VERSION = 1
VERSION_PROOF = 2                        # update payload v2: v1 fields + proof_hash (Phase 3, D-018)
KIND_UPDATE, KIND_VOTE = 1, 2
TAGS = {KIND_UPDATE: b"QSFL-env-v1", KIND_VOTE: b"QSFL-vote-v1"}
_HEAD = struct.Struct("<BBII")           # version, kind, round, id
UPDATE_LEN = _HEAD.size + 4 * 32
UPDATE_LEN_V2 = UPDATE_LEN + 32
VOTE_LEN = _HEAD.size + 3 * 32


def model_hash(w):
    return hashlib.sha256(np.asarray(w, dtype="<i8").tobytes()).digest()


def commit(delta, nonce):
    """Update commitment C_i = SHA256("QSFL-upd" || delta_le || nonce)."""
    return hashlib.sha256(b"QSFL-upd" + np.asarray(delta, dtype="<i8").tobytes() + nonce).digest()


def make_nonce(seed, rnd, ident, kind=KIND_UPDATE):
    """Deterministic 32-byte nonce (seeded experiments)."""
    return hashlib.sha256(b"QSFL-nonce" + struct.pack("<QIIB", seed, rnd, ident, kind)).digest()


def proof_hash(receipt_bytes):
    """proof_hash = SHA256 of the receipt file bytes (docs/zk_interface.md section 8)."""
    return hashlib.sha256(receipt_bytes).digest()


def pack_update(rnd, client_id, h_w, c, r, nonce, proof_hash=None):
    """v1 payload, or v2 (version byte 2, proof_hash appended) when `proof_hash` is given."""
    assert all(len(x) == 32 for x in (h_w, c, r, nonce))
    if proof_hash is None:
        return _HEAD.pack(VERSION, KIND_UPDATE, rnd, client_id) + h_w + c + r + nonce
    assert len(proof_hash) == 32
    return _HEAD.pack(VERSION_PROOF, KIND_UPDATE, rnd, client_id) + h_w + c + r + nonce + proof_hash


def parse_update(p):
    """-> dict, or None when the bytes are not a well-formed update payload."""
    if len(p) < _HEAD.size:
        return None
    v, k, rnd, cid = _HEAD.unpack_from(p)
    if k != KIND_UPDATE or (v, len(p)) not in ((VERSION, UPDATE_LEN), (VERSION_PROOF, UPDATE_LEN_V2)):
        return None
    o = _HEAD.size
    return dict(round=rnd, client_id=cid, h_w=p[o:o + 32], c=p[o + 32:o + 64], r=p[o + 64:o + 96], nonce=p[o + 96:o + 128],
                version=v, proof_hash=p[o + 128:o + 160] if v == VERSION_PROOF else None)


def pack_vote(rnd, agg_id, h_next, set_hash, nonce):
    assert all(len(x) == 32 for x in (h_next, set_hash, nonce))
    return _HEAD.pack(VERSION, KIND_VOTE, rnd, agg_id) + h_next + set_hash + nonce


def parse_vote(p):
    if len(p) != VOTE_LEN:
        return None
    v, k, rnd, aid = _HEAD.unpack_from(p)
    if v != VERSION or k != KIND_VOTE:
        return None
    o = _HEAD.size
    return dict(round=rnd, agg_id=aid, h_next=p[o:o + 32], set_hash=p[o + 32:o + 64], nonce=p[o + 64:o + 96])


def payload_kind(p):
    return p[1] if len(p) >= 2 else None


def signed_bytes(kind, alg, payload):
    a = alg.encode()
    return TAGS[kind] + bytes([len(a)]) + a + payload


@dataclass
class Envelope:
    payload: bytes
    sigs: list = field(default_factory=list)   # [(alg, key_id, signature)]

    def wire(self):
        out = [self.payload, bytes([len(self.sigs)])]
        for alg, kid, s in self.sigs:
            a, k = alg.encode(), kid.encode()
            out += [bytes([len(a)]), a, bytes([len(k)]), k, struct.pack("<H", len(s)), s]
        return b"".join(out)

    @classmethod
    def from_wire(cls, b, payload_len):
        """-> Envelope or None if malformed."""
        try:
            p, n, i = b[:payload_len], b[payload_len], payload_len + 1
            sigs = []
            for _ in range(n):
                la = b[i]; a = b[i + 1:i + 1 + la].decode(); i += 1 + la
                lk = b[i]; k = b[i + 1:i + 1 + lk].decode(); i += 1 + lk
                (ls,) = struct.unpack_from("<H", b, i); s = b[i + 2:i + 2 + ls]; i += 2 + ls
                if len(s) != ls:
                    return None
                sigs.append((a, k, s))
            return cls(p, sigs) if i == len(b) else None
        except (IndexError, UnicodeDecodeError, struct.error):
            return None

    def overhead(self):
        """Bytes the signature layer adds on top of the payload (count, algs, key ids, signatures)."""
        return len(self.wire()) - len(self.payload)


def sign_payload(registry, role, ident, algs, payload):
    """Sign `payload` with the node's current-epoch key for each alg in `algs`."""
    kind = payload_kind(payload)
    out = []
    for alg in algs:
        sk = registry.secret_key(role, ident, alg)
        out.append((alg, registry.key_id(role, ident, alg), sig.sign(alg, sk, signed_bytes(kind, alg, payload))))
    return Envelope(payload, out)


def sign_update(registry, algs, rnd, client_id, h_w, delta, root, nonce, proof_hash=None):
    """Client side. `algs` = [] gives an unsigned envelope (used to test the 'unsigned' path).
    `proof_hash` (SHA256 of the receipt) makes it a v2 envelope."""
    payload = pack_update(rnd, client_id, h_w, commit(delta, nonce), root, nonce, proof_hash)
    return sign_payload(registry, "client", client_id, algs, payload)
