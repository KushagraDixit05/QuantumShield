"""Attacks on the signed-envelope layer (distinct from the update-poisoning attacks in poison.py).

What signatures do and do NOT stop:
- replay_envelope: the old envelope resent verbatim. Stopped (wrong round / nonce reuse).
- tamper_delta: update altered after signing. Stopped (commitment C_i no longer matches).
- forge_*: attacker holds a victim's Ed25519 secret key (SIMULATION of what a quantum adversary
  running Shor's algorithm would recover from the public key; no quantum computer is involved).
  Accepted under `classical`, rejected under `pq` and `hybrid`.
- A malicious client signing its OWN poisoned or stale update with its own valid key is NOT
  stopped by signatures. That is the job of the norm check / ZK proof (see docs/zk_statement.md).
"""
import numpy as np

from pq import envelope as ev
from pq import sig


def tamper_delta(env, d):
    d2 = np.array(d, dtype=np.int64)
    d2[0] += 1
    return env, d2


def forge_with_classical_key(session, victim, t, d_forged, stripped=False):
    """Build an envelope for `victim` carrying `d_forged`, using only the victim's Ed25519 secret key.

    Best effort against a PQ/hybrid verifier: attach a same-length random 'signature' under the
    victim's PQ key id (junk) or, if `stripped`, send the Ed25519 signature alone (downgrade attempt).
    """
    reg, ident = session.registry, victim
    payload = ev.pack_update(t, ident, session.h_w, ev.commit(d_forged, nonce := ev.make_nonce(session.seed + 7919, t, ident)),
                             session.roots[ident], nonce)
    sigs = []
    # junk variant: one signature per algorithm the verifier requires; stripped: Ed25519 only
    for alg in (reg.algs if stripped else session.algs):
        kid = reg.key_id("client", ident, alg)
        if sig.kind(alg) == "classical":      # the compromised key: valid signature
            sk = reg.secret_key("client", ident, alg)
            sigs.append((alg, kid, sig.sign(alg, sk, ev.signed_bytes(ev.KIND_UPDATE, alg, payload))))
        elif not stripped:                    # no PQ secret key: junk of the right length
            sigs.append((alg, kid, sig.rand_bytes(sig.sizes(alg)[1])))
    return ev.Envelope(payload, sigs), d_forged


def swap_proof(session, t, client_b, d_b, receipt_a, hash_matches=True):
    """Proof swapped from another client. Client B's update `d_b` is submitted with client A's valid receipt.

    Returns (env, delta, receipt): exactly what the aggregator receives (feed to Session.admit / Verifier.verify_envelope).
    - hash_matches=True: B signs an envelope whose proof_hash is SHA256(A's receipt bytes), so the hash check
      passes and the journal check catches it: the receipt journal holds A's client id and commitment.
      Expected reason: bad_proof:journal_mismatch.
    - hash_matches=False: B's envelope carries the hash of B's own (absent or different) receipt, A's bytes are
      attached: bad_proof:hash_mismatch.
    Signatures are B's own and valid; only the proof binding stops this.
    """
    own = receipt_a if hash_matches else b"client-B-own-receipt-absent"
    env = session.client_envelope(t, client_b, d_b, receipt=own)
    return env, d_b, receipt_a
