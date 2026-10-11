"""sklearn digits -> fixed-point inputs, seeded IID client split, shared test set."""
from dataclasses import dataclass

import numpy as np
from sklearn.datasets import load_digits

from .fixedpoint import SCALE_BITS


@dataclass
class Dataset:
    X: np.ndarray  # (n, 64) int64 fixed point, pixel p -> p << 12
    y: np.ndarray  # (n,) int64 labels

    def __len__(self):
        return len(self.y)


def load(seed, n_clients, test_frac=0.2):
    """Returns (list of per-client Dataset, shared test Dataset). Split depends only on `seed`."""
    d = load_digits()
    X = d.data.astype(np.int64) << (SCALE_BITS - 4)  # pixels are 0..16 -> exact
    y = d.target.astype(np.int64)
    perm = np.random.default_rng(seed).permutation(len(y))
    X, y = X[perm], y[perm]
    n_test = int(len(y) * test_frac)
    test = Dataset(X[:n_test], y[:n_test])
    Xt, yt = X[n_test:], y[n_test:]
    shards = np.array_split(np.arange(len(yt)), n_clients)
    return [Dataset(Xt[s], yt[s]) for s in shards], test
