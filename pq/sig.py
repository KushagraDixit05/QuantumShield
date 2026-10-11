"""Signature wrapper: ML-DSA-44/65, Falcon-512, SLH-DSA-128s (liboqs) and Ed25519 (cryptography).

keygen / sign / verify only. Real liboqs calls, no stubs. verify() never raises: any malformed
input is just `False`.

Randomness: liboqs-python has no seeded keygen, so seed_rng() installs liboqs's custom RNG hook
(OQS_randombytes_custom_algorithm) fed by a SHA-256 counter stream. With a seed, keys AND
signatures (ML-DSA/Falcon/SLH-DSA sign with fresh randomness) are reproducible, as long as calls
happen in a fixed order in one thread. seed_rng(None) restores the system RNG.
"""
import ctypes as ct
import hashlib
import os

import oqs
import oqs.rand
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

# config name -> (kind, liboqs mechanism name)
SCHEMES = {
    "Ed25519": ("classical", None),
    "ML-DSA-44": ("pq", "ML-DSA-44"),
    "ML-DSA-65": ("pq", "ML-DSA-65"),
    "Falcon-512": ("pq", "Falcon-512"),
    "SLH-DSA-128s": ("pq", "SLH_DSA_PURE_SHA2_128S"),  # FIPS 205 SLH-DSA-SHA2-128s, pure (not pre-hash)
}
PQ_ALGS = [a for a, (k, _) in SCHEMES.items() if k == "pq"]
CLASSICAL_ALGS = [a for a, (k, _) in SCHEMES.items() if k == "classical"]


def kind(alg):
    return SCHEMES[alg][0]


# --- seeded randomness -------------------------------------------------------------------------
class _Stream:
    def __init__(self, seed):
        self.seed, self.ctr, self.buf = seed, 0, b""

    def read(self, n):
        while len(self.buf) < n:
            self.buf += hashlib.sha256(b"QSFL-rng" + self.seed + self.ctr.to_bytes(8, "little")).digest()
            self.ctr += 1
        out, self.buf = self.buf[:n], self.buf[n:]
        return out


_CB = ct.CFUNCTYPE(None, ct.POINTER(ct.c_uint8), ct.c_size_t)
_stream = None


def _fill(ptr, n):
    ct.memmove(ptr, _stream.read(n), n)


_cb = _CB(_fill)  # module-level reference: must outlive every liboqs call


def seed_rng(seed):
    """Make all following keygen/sign calls deterministic (int or bytes seed), or None for system RNG."""
    global _stream
    if seed is None:
        _stream = None
        oqs.rand.randombytes_switch_algorithm("system")
        return
    if isinstance(seed, int):
        seed = seed.to_bytes(16, "little", signed=True)
    _stream = _Stream(bytes(seed))
    lib = oqs.native()
    lib.OQS_randombytes_custom_algorithm.argtypes = [_CB]
    lib.OQS_randombytes_custom_algorithm(_cb)


def rand_bytes(n):
    return _stream.read(n) if _stream is not None else os.urandom(n)


# --- keygen / sign / verify --------------------------------------------------------------------
def _oqs_name(alg):
    return SCHEMES[alg][1]


def keygen(alg):
    """Returns (public_key, secret_key) as bytes."""
    if alg not in SCHEMES:
        raise ValueError(f"unknown signature algorithm {alg!r}")
    if kind(alg) == "classical":
        sk = Ed25519PrivateKey.from_private_bytes(rand_bytes(32))
        return (sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
                sk.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
    with oqs.Signature(_oqs_name(alg)) as s:
        pk = s.generate_keypair()
        return bytes(pk), bytes(s.export_secret_key())


def sign(alg, sk, msg):
    if kind(alg) == "classical":
        return Ed25519PrivateKey.from_private_bytes(sk).sign(msg)
    with oqs.Signature(_oqs_name(alg), secret_key=sk) as s:
        return bytes(s.sign(msg))


def verify(alg, pk, msg, sig):
    try:
        if kind(alg) == "classical":
            Ed25519PublicKey.from_public_bytes(pk).verify(sig, msg)
            return True
        with oqs.Signature(_oqs_name(alg)) as s:
            return bool(s.verify(msg, sig, pk))
    except (InvalidSignature, ValueError, TypeError, RuntimeError, OverflowError, KeyError):
        return False


def sizes(alg):
    """(public key bytes, signature bytes) as specified by the scheme (max length for Falcon)."""
    if kind(alg) == "classical":
        return 32, 64
    with oqs.Signature(_oqs_name(alg)) as s:
        return s.details["length_public_key"], s.details["length_signature"]
