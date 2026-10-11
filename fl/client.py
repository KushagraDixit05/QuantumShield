"""Deterministic local training: K integer SGD steps on publicly-seeded samples."""
import hashlib

import numpy as np

from . import fixedpoint as fx
from . import model


def sample_indices(seed, rnd, client, K, batch, n):
    """idx[s, j] = u64_le(SHA256("QSFL-idx" || seed(u64) || t || c || s || j (u32 LE))[:8]) mod n."""
    out = np.empty((K, batch), dtype=np.int64)
    for s in range(K):
        for j in range(batch):
            h = hashlib.sha256(b"QSFL-idx" + int(seed).to_bytes(8, "little")
                               + b"".join(int(v).to_bytes(4, "little") for v in (rnd, client, s, j))).digest()
            out[s, j] = int.from_bytes(h[:8], "little") % n
    return out


def grad(w, X, y):
    """Mean one-hot-MSE gradient over the batch (batch must be a power of two), fixed point."""
    B = len(y)
    shift = B.bit_length() - 1
    assert 1 << shift == B
    W1, b1, W2, b2 = model.unflatten(w)
    pre, h, out = model.forward(w, X)
    target = np.zeros_like(out)
    target[np.arange(B), y] = fx.ONE
    dout = out - target                                   # (B,10)
    dh = fx.sum_prod_shift(dout, W2) * (pre > 0)          # (B,32)
    gW2 = fx.sum_prod_shift(dout.T, h) >> shift
    gW1 = fx.sum_prod_shift(dh.T, X) >> shift
    return model.flatten(gW1, dh.sum(0) >> shift, gW2, dout.sum(0) >> shift)


def local_train(w0, ds, idx, lr_fx):
    """K SGD steps from w0 on ds[idx[s]]; returns Δ = W_K - W_0 (int64, N_PARAMS)."""
    w = np.array(w0, dtype=np.int64)
    for s in range(len(idx)):
        g = grad(w, ds.X[idx[s]], ds.y[idx[s]])
        w = w - fx.fx_mul(np.int64(lr_fx), g)
    return w - w0
