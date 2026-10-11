"""Poisoning attacks on a single malicious client. All operate in fixed point.

Each docstring states what catches it and what does not. See docs/zk_statement.md.
"""
import numpy as np

from fl.data import Dataset


def scaled(delta, s=50):
    """Δ * s. Caught by the norm bound (B) once s*||Δ|| > B. Breaks plain FedAvg."""
    return np.asarray(delta, dtype=np.int64) * int(s)


def sign_flip(delta, s=1):
    """-s * Δ. With s ~ 1 the norm equals a benign one, so the norm bound does NOT catch it;
    the ZK consistency clause (c) would, since -Δ is not the result of SGD on committed data.
    With s large enough to exceed B the norm bound catches it."""
    return -int(s) * np.asarray(delta, dtype=np.int64)


def label_flip(ds, shift=1):
    """Return a copy of the client's data with every label y -> (y+shift) % 10.
    The client then trains honestly. The update is in-norm and consistent with its own
    committed (poisoned) data, so neither the norm bound nor the SGD-consistency proof
    catches it. Only robust aggregation / data attestation can help."""
    return Dataset(ds.X, (ds.y + shift) % 10)


def replay(history):
    """Resubmit the client's own update from the previous round (history = list of past
    submitted updates; returns None when there is nothing to replay). The FL layer cannot
    tell it from a fresh one; it is rejected only by round-bound, nonce-tracked signed
    envelopes and by the proof's public inputs (H(W_t), t) (Phase 2/3)."""
    return history[-1].copy() if history else None
