"""Cost-probe input builder (lead-owned, throwaway). Builds the docs/zk_interface.md input frame
from the existing Phase 1 code. usage: make_input.py out.bin K batch [relation]"""
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fl import client, data, merkle, model  # noqa: E402
from fl import fixedpoint as fx  # noqa: E402
from pq import envelope as ev  # noqa: E402


def build(K, batch, rel=1, seed=0, t=0, c=0, lr=0.3, B=1.5963, n_clients=5):
    clients, _ = data.load(seed, n_clients)
    ds = clients[c]
    n = len(ds)
    w0 = model.init(seed)
    lr_fx = int(fx.to_fx(lr))
    idx = client.sample_indices(seed, t, c, K, batch, n)
    delta = client.local_train(w0, ds, idx, lr_fx)
    tree = merkle.MerkleTree(ds.X, ds.y)
    nonce = ev.make_nonce(seed, t, c)
    B2 = fx.bound_sq(B)
    if rel == 2:
        K = batch = 0
    out = b"QSZK" + bytes([1, rel]) + struct.pack("<IIIII", t, c, n, K, batch)
    out += struct.pack("<QqQ", seed, lr_fx, B2)
    out += ev.model_hash(w0) + ev.commit(delta, nonce) + tree.root + nonce
    assert len(out) == 178
    if rel == 1:
        out += w0.astype("<i8").tobytes()
    out += delta.astype("<i8").tobytes()
    if rel == 1:
        order = list(dict.fromkeys(int(i) for i in idx.ravel()))
        out += struct.pack("<I", len(order))
        for i in order:
            out += struct.pack("<I", i) + ds.X[i].astype("<i8").tobytes() + struct.pack("<I", int(ds.y[i]))
            out += b"".join(tree.path(i))
    return out, dict(n=n, unique=len(set(idx.ravel().tolist())), norm2=fx.norm_sq(delta), B2=B2)


if __name__ == "__main__":
    o, K, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    rel = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    blob, info = build(K, b, rel)
    Path(o).write_bytes(blob)
    print(len(blob), info)
