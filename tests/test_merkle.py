import numpy as np

from fl import merkle


def _data(n):
    rng = np.random.default_rng(1)
    return rng.integers(0, 1 << 16, (n, 64)).astype(np.int64), rng.integers(0, 10, n)


def test_all_paths_verify_odd_and_even():
    for n in (1, 2, 5, 8, 37):
        X, y = _data(n)
        t = merkle.MerkleTree(X, y)
        for i in range(n):
            assert merkle.verify(t.root, n, i, X[i], y[i], t.path(i))


def test_tampered_leaf_label_path_index_rejected():
    X, y = _data(9)
    t = merkle.MerkleTree(X, y)
    p = t.path(3)
    bad_x = X[3].copy(); bad_x[0] ^= 1
    assert not merkle.verify(t.root, 9, 3, bad_x, y[3], p)
    assert not merkle.verify(t.root, 9, 3, X[3], (y[3] + 1) % 10, p)
    bad_p = list(p); bad_p[0] = bytes(32)
    assert not merkle.verify(t.root, 9, 3, X[3], y[3], bad_p)
    assert not merkle.verify(t.root, 9, 4, X[3], y[3], p)
    assert not merkle.verify(t.root, 9, 99, X[3], y[3], p)
