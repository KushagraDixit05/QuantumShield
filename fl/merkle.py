"""SHA-256 Merkle tree over client samples (domain-separated leaves and nodes)."""
import hashlib

import numpy as np


def _h(b):
    return hashlib.sha256(b).digest()


def leaf_bytes(x, y):
    return np.asarray(x, dtype="<i8").tobytes() + int(y).to_bytes(4, "little")


def leaf_hash(x, y):
    return _h(b"\x00" + leaf_bytes(x, y))


def _node(l, r):
    return _h(b"\x01" + l + r)


def _levels(leaves):
    level = list(leaves)
    levels = [level]
    while len(level) > 1:
        if len(level) % 2:
            level = level + [level[-1]]  # duplicate last node; leaf count is public
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        levels.append(level)
    return levels


class MerkleTree:
    def __init__(self, X, y):
        assert len(X) == len(y) and len(X) > 0
        self.n = len(X)
        self.levels = _levels([leaf_hash(X[i], y[i]) for i in range(self.n)])
        self.root = self.levels[-1][0]

    def path(self, i):
        out = []
        for level in self.levels[:-1]:
            lv = level + [level[-1]] if len(level) % 2 else level
            out.append(lv[i ^ 1])
            i //= 2
        return out


def verify(root, n, i, x, y, path):
    if not 0 <= i < n:
        return False
    h = leaf_hash(x, y)
    for sib in path:
        h = _node(h, sib) if i % 2 == 0 else _node(sib, h)
        i //= 2
    return h == root
