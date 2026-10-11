"""Integer MLP 64->32->10 (ReLU hidden, linear output) on a flat int64 parameter vector."""
import numpy as np

from . import fixedpoint as fx

D_IN, D_H, D_OUT = 64, 32, 10
SIZES = [(D_H * D_IN), D_H, (D_OUT * D_H), D_OUT]
N_PARAMS = sum(SIZES)  # 2410


def unflatten(w):
    w = np.asarray(w)
    assert w.shape == (N_PARAMS,)
    o = np.cumsum([0] + SIZES)
    return (w[o[0]:o[1]].reshape(D_H, D_IN), w[o[1]:o[2]],
            w[o[2]:o[3]].reshape(D_OUT, D_H), w[o[3]:o[4]])


def flatten(W1, b1, W2, b2):
    return np.concatenate([W1.ravel(), b1, W2.ravel(), b2]).astype(np.int64)


def init(seed):
    """Public, deterministic initial global model. Weights ~ N(0, 0.1^2): He scale made the
    round-0 updates large and seed-dependent (see docs/decisions.md D-011)."""
    rng = np.random.default_rng(seed)
    W1 = rng.normal(0, 0.1, (D_H, D_IN))
    W2 = rng.normal(0, 0.1, (D_OUT, D_H))
    return flatten(fx.to_fx(W1), np.zeros(D_H, np.int64), fx.to_fx(W2), np.zeros(D_OUT, np.int64))


def forward(w, X):
    """Batched forward. X: (B,64) fixed point. Returns (pre-activation h, h, out)."""
    W1, b1, W2, b2 = unflatten(w)
    pre = fx.sum_prod_shift(X, W1.T) + b1
    h = np.maximum(pre, 0)
    out = fx.sum_prod_shift(h, W2.T) + b2
    return pre, h, out


def predict(w, X):
    return np.argmax(forward(w, X)[2], axis=1)


def accuracy(w, ds):
    return float(np.mean(predict(w, ds.X) == ds.y))
