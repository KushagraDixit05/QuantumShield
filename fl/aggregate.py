"""Aggregation rules over int64 fixed-point updates. All integer, floor semantics.

Each rule returns the aggregated Δ (to be added to the global model).
"""
import numpy as np

from . import fixedpoint as fx


def fedavg(deltas):
    """Plain mean (floor). Catches nothing: one large update dominates."""
    return np.sum(deltas, axis=0) // len(deltas)


def accepted_by_norm(deltas, B2):
    """Plaintext policy check ||Δ||^2 <= B^2. This is the check the ZK proof will later
    enforce without revealing the witness; here it is only a plain comparison, NOT a proof."""
    def ok(d):
        try:
            return fx.norm_sq(d) <= B2
        except fx.FixedPointOverflow:  # unprovable by the statement => reject
            return False
    return [ok(d) for d in deltas]


def norm_filter_mean(deltas, B2):
    """Drop updates violating the norm bound, then FedAvg the rest (0 if none remain).
    Catches: oversized (scaled) updates. Misses: any update inside the bound
    (sign-flip at scale ~1, label-flip, replay of a benign update)."""
    keep = [d for d, ok in zip(deltas, accepted_by_norm(deltas, B2)) if ok]
    if not keep:
        return np.zeros_like(deltas[0])
    return fedavg(keep)


def coord_median(deltas):
    """Coordinate-wise median (mean of two middle values, floor, for even counts).
    Tolerates < n/2 arbitrary updates per coordinate, but needs plaintext Δ and has no
    proof of anything; slows convergence on honest data."""
    s = np.sort(np.stack(deltas), axis=0)
    n = len(deltas)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) >> 1


def clip_mean(deltas, B2):
    """Scale oversized updates down to norm bound (integer sqrt) then average."""
    out = []
    for d in deltas:
        n2 = fx.norm_sq(d)
        if n2 <= B2:
            out.append(d)
        else:
            # d * floor(B / ||d|| in fx) ; isqrt keeps it exact-integer
            from math import isqrt
            ratio = (isqrt(B2) << fx.SCALE_BITS) // isqrt(n2)
            out.append(fx.fx_mul(d, np.int64(ratio)))
    return fedavg(out)


DEFENCES = {"fedavg": lambda ds, B2: fedavg(ds),
            "norm_filter": norm_filter_mean,
            "median": lambda ds, B2: coord_median(ds),
            "clip": clip_mean}
