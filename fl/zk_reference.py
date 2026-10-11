"""Independent pure-Python reference of the whole Phase 3 relation (docs/zk_interface.md).

Deliberately does NOT use fl.client.local_train / fl.fixedpoint for the SGD path: the guard rule,
checked i64 arithmetic (raises, never wraps), the SGD step order (section 4), sampling (5),
strict Merkle (6), commitment, norm and every well-formedness check are re-implemented here.
`evaluate(blob)` returns exactly what the guest decides: (ok, journal | None, reason).
No floats anywhere in this module.
"""
import hashlib
import struct

import numpy as np

SCALE_BITS = 16
ONE = 1 << SCALE_BITS
LIMIT = 1 << 62
I64_MIN, I64_MAX = -(1 << 63), (1 << 63) - 1
D_IN, D_H, D_OUT = 64, 32, 10
SIZES = (D_H * D_IN, D_H, D_OUT * D_H, D_OUT)
N_PARAMS = sum(SIZES)  # 2410
HEAD_LEN = 146
PRIV_OFF = 178
MAGIC = b"QSZK"
B2_MAX = 1 << 50
ENTRY_CAP = 1 << 25
LEAF_LEN = D_IN * 8 + 4


class Reject(Exception):
    """The guest would fail; `.reason` is a short machine-readable tag."""

    def __init__(self, reason, detail=""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def _sha(b):
    return hashlib.sha256(b).digest()


def depth(n_c):
    """ceil(log2(n_c)); 0 for n_c = 1."""
    return (n_c - 1).bit_length()


# ---------------------------------------------------------------- checked arithmetic
def ck(a):
    """Checked i64: raise Reject('overflow') if any entry of the Python-int array leaves i64."""
    a = np.asarray(a, dtype=object)
    for v in a.ravel():
        if v < I64_MIN or v > I64_MAX:
            raise Reject("overflow", "i64 overflow")
    return a


def _obj(a):
    return np.asarray(a, dtype=object)


def add(a, b):
    return ck(_obj(a) + _obj(b))


def sub(a, b):
    return ck(_obj(a) - _obj(b))


def _maxabs(a):
    a = _obj(a)
    return max((abs(int(v)) for v in a.ravel()), default=0)


def _guard(a, b, terms):
    """Fail iff max|a| * max|b| * terms >= 2^62 (unbounded Python ints = u128)."""
    if _maxabs(a) * _maxabs(b) * terms >= LIMIT:
        raise Reject("guard", "product guard >= 2^62")


def sum_prod_shift(A, B):
    """(A @ B) >> 16 with the guard; terms = A.shape[-1]. Exact Python-int accumulation."""
    A, B = _obj(A), _obj(B)
    _guard(A, B, A.shape[-1])
    return ck((A.dot(B)) >> SCALE_BITS)  # object dot = exact; >> on Python ints floors


def fx_mul(a, b):
    a, b = _obj(a), _obj(b)
    _guard(a, b, 1)
    return ck((a * b) >> SCALE_BITS)


# ---------------------------------------------------------------- model / SGD
def unflatten(w):
    w = _obj(w)
    o = [0]
    for s in SIZES:
        o.append(o[-1] + s)
    return (w[o[0]:o[1]].reshape(D_H, D_IN), w[o[1]:o[2]],
            w[o[2]:o[3]].reshape(D_OUT, D_H), w[o[3]:o[4]])


def flatten(W1, b1, W2, b2):
    return np.concatenate([W1.ravel(), b1, W2.ravel(), b2])


def sgd_step(w, X, y, lr_fx):
    """One step, section 4 order. w: N_PARAMS Python ints; X (B,64); y (B,). Returns new w (object array)."""
    X, y = _obj(X), [int(v) for v in y]
    B = len(y)
    if B < 1 or B & (B - 1):
        raise Reject("bad_batch")
    if any(v < 0 or v >= D_OUT for v in y):
        raise Reject("label_range", "label >= 10")
    shift = B.bit_length() - 1
    W1, b1, W2, b2 = unflatten(w)
    pre = add(sum_prod_shift(X, W1.T), b1[None, :])                     # 1
    h = np.where(pre > 0, pre, 0).astype(object)                       # 2
    out = add(sum_prod_shift(h, W2.T), b2[None, :])                     # 3
    target = np.zeros((B, D_OUT), dtype=object)
    for i, lab in enumerate(y):
        target[i, lab] = ONE
    dout = sub(out, target)                                             # 4
    dh = sum_prod_shift(dout, W2) * (pre > 0).astype(object)            # 5
    dh = ck(dh)
    gW2 = sum_prod_shift(dout.T, h) >> shift                            # 6
    gW1 = sum_prod_shift(dh.T, X) >> shift                              # 7
    gb1 = ck(dh.sum(axis=0)) >> shift                                   # 8
    gb2 = ck(dout.sum(axis=0)) >> shift
    g = flatten(gW1, gb1, gW2, gb2)                                     # 9
    return sub(w, fx_mul(np.array([lr_fx], dtype=object), g))


def run_sgd(w0, X_steps, y_steps, lr_fx):
    """K steps from w0. X_steps (K,batch,64), y_steps (K,batch). Returns W_K (object array of ints)."""
    w = ck(_obj(w0))
    for s in range(len(y_steps)):
        w = sgd_step(w, X_steps[s], y_steps[s], int(lr_fx))
    return w


def sample_indices(seed, t, c, K, batch, n_c):
    """Section 5. Returns list of K lists of `batch` ints."""
    out = []
    for s in range(K):
        row = []
        for j in range(batch):
            d = _sha(b"QSFL-idx" + struct.pack("<QIIII", seed, t, c, s, j))
            row.append(int.from_bytes(d[:8], "little") % n_c)
        out.append(row)
    return out


def unique_in_order(idx):
    return list(dict.fromkeys(i for row in idx for i in row))


# ---------------------------------------------------------------- hashes / merkle
def model_hash(w):
    return _sha(_le64(w))


def commit(delta, nonce):
    return _sha(b"QSFL-upd" + _le64(delta) + nonce)


def _le64(a):
    return b"".join(int(v).to_bytes(8, "little", signed=True) for v in np.asarray(a, dtype=object).ravel())


def leaf_hash(x, y):
    return _sha(b"\x00" + _le64(x) + int(y).to_bytes(4, "little"))


def _node(l, r):
    return _sha(b"\x01" + l + r)


def merkle_levels(leaves):
    level, levels = list(leaves), []
    levels.append(level)
    while len(level) > 1:
        if len(level) % 2:
            level = level + [level[-1]]
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        levels.append(level)
    return levels


def merkle_root_and_paths(X, y):
    """Root and per-index sibling lists (leaf level first) of the strict tree."""
    levels = merkle_levels([leaf_hash(X[i], y[i]) for i in range(len(y))])
    paths = []
    for i in range(len(y)):
        p, k = [], i
        for lv in levels[:-1]:
            lv = lv + [lv[-1]] if len(lv) % 2 else lv
            p.append(lv[k ^ 1])
            k //= 2
        paths.append(p)
    return levels[-1][0], paths


def merkle_check(root, n_c, i, x, y, path):
    """Strict: i < n_c and exactly depth(n_c) siblings."""
    if not 0 <= i < n_c or len(path) != depth(n_c):
        return False
    h = leaf_hash(x, y)
    for sib in path:
        h = _node(h, sib) if i % 2 == 0 else _node(sib, h)
        i //= 2
    return h == root


# ---------------------------------------------------------------- input blob
def build_input(*, relation=1, t, c, n_c, K, batch, seed, lr_fx, B2, h_w, C, R, nonce,
                w_t=None, delta, openings=(), magic=MAGIC, version=1, n_open=None):
    """Serialise section 2. openings: iterable of (index, x(64), label, [sibling32...]).
    Every field can be given wrong on purpose (tests build negative inputs with this)."""
    if relation == 2:
        K, batch = (K, batch)  # caller passes 0, 0 for a well-formed relation 2; not forced here
    out = magic + bytes([version, relation]) + struct.pack("<IIIII", t, c, n_c, K, batch)
    out += struct.pack("<Qq", seed, lr_fx) + struct.pack("<Q", B2)
    out += h_w + C + R + nonce
    if relation == 1:
        out += _le64(w_t)
    out += _le64(delta)
    if relation == 1:
        openings = list(openings)
        out += struct.pack("<I", len(openings) if n_open is None else n_open)
        for idx, x, lab, path in openings:
            out += struct.pack("<I", idx) + _le64(x) + struct.pack("<I", lab) + b"".join(path)
    return out


def parse_input(blob):
    """-> dict of fields. Raises Reject on malformed structure. `openings` is a list of
    (index, x ints, label, [siblings])."""
    if len(blob) < HEAD_LEN + 32:
        raise Reject("truncated", "shorter than header")
    if blob[:4] != MAGIC:
        raise Reject("bad_magic")
    if blob[4] != 1:
        raise Reject("bad_version")
    rel = blob[5]
    if rel not in (1, 2):
        raise Reject("bad_relation")
    t, c, n_c, K, batch = struct.unpack_from("<IIIII", blob, 6)
    seed, = struct.unpack_from("<Q", blob, 26)
    lr_fx, = struct.unpack_from("<q", blob, 34)
    B2, = struct.unpack_from("<Q", blob, 42)
    p = dict(relation=rel, t=t, c=c, n_c=n_c, K=K, batch=batch, seed=seed, lr_fx=lr_fx, B2=B2,
             h_w=blob[50:82], C=blob[82:114], R=blob[114:146], nonce=blob[146:178])
    if B2 >= B2_MAX:
        raise Reject("b2_too_large")
    if lr_fx <= 0:
        raise Reject("bad_lr")
    if n_c < 1:
        raise Reject("bad_n_c")
    if rel == 1:
        if K < 1:
            raise Reject("bad_K")
        if batch < 1 or batch & (batch - 1):
            raise Reject("bad_batch")
    elif K != 0 or batch != 0:
        raise Reject("bad_params", "relation 2 needs K = batch = 0")
    pos = PRIV_OFF
    nbytes = N_PARAMS * 8

    def take(n):
        nonlocal pos
        if pos + n > len(blob):
            raise Reject("truncated")
        r = blob[pos:pos + n]
        pos += n
        return r

    def ints(b):
        return [int.from_bytes(b[i:i + 8], "little", signed=True) for i in range(0, len(b), 8)]

    p["w_t"] = ints(take(nbytes)) if rel == 1 else None
    p["delta"] = ints(take(nbytes))
    p["openings"] = []
    if rel == 1:
        n_open, = struct.unpack("<I", take(4))
        p["n_open"] = n_open
        d = depth(n_c)
        osz = 4 + D_IN * 8 + 4 + 32 * d
        if n_open > (len(blob) - pos) // osz + 1:
            raise Reject("truncated", "opening count exceeds blob")
        for _ in range(n_open):
            o = take(osz)
            idx, = struct.unpack_from("<I", o, 0)
            x = ints(o[4:4 + D_IN * 8])
            lab, = struct.unpack_from("<I", o, 4 + D_IN * 8)
            sib = [o[8 + D_IN * 8 + 32 * k: 8 + D_IN * 8 + 32 * (k + 1)] for k in range(d)]
            p["openings"].append((idx, x, lab, sib))
    if pos != len(blob):
        raise Reject("trailing_bytes")
    return p


def journal_for(*, relation=1, t, c, n_c, K, batch, seed, lr_fx, B2, h_w, C, R):
    """The 146-byte journal (same as pq.zkpolicy.expected_public)."""
    if relation == 2:
        K = batch = 0
    return (MAGIC + bytes([1, relation]) + struct.pack("<IIIII", t, c, n_c, K, batch)
            + struct.pack("<QqQ", seed, lr_fx, B2) + h_w + C + R)


# ---------------------------------------------------------------- the relation
def _check(blob):
    p = parse_input(blob)
    delta = p["delta"]
    if commit(delta, p["nonce"]) != p["C"]:
        raise Reject("commitment_mismatch")
    if max(abs(v) for v in delta) >= ENTRY_CAP:
        raise Reject("norm_entry_cap")
    if sum(v * v for v in delta) > p["B2"]:
        raise Reject("norm_exceeded")
    if p["relation"] == 1:
        _check_training(p)
    return p


def _check_training(p):
    w_t, n_c, K, batch = p["w_t"], p["n_c"], p["K"], p["batch"]
    if model_hash(w_t) != p["h_w"]:
        raise Reject("model_hash_mismatch")
    idx = sample_indices(p["seed"], p["t"], p["c"], K, batch, n_c)
    order = unique_in_order(idx)
    if p["n_open"] != len(order):
        raise Reject("bad_opening_count", f"{p['n_open']} openings, {len(order)} distinct indices")
    recs = {}
    for want, (i, x, lab, path) in zip(order, p["openings"]):
        if i != want:
            raise Reject("opening_index_mismatch", f"expected {want}, got {i}")
        if not merkle_check(p["R"], n_c, i, x, lab, path):
            raise Reject("bad_merkle_path", f"index {i}")
        recs[i] = (x, lab)
    X = [[recs[i][0] for i in row] for row in idx]
    y = [[recs[i][1] for i in row] for row in idx]
    wk = run_sgd(w_t, X, y, p["lr_fx"])
    if any(int(a) - int(b) != d for a, b, d in zip(wk, w_t, p["delta"])):
        raise Reject("delta_mismatch")


def evaluate(blob):
    """(ok, journal | None, reason). Reason is 'ok' on success."""
    try:
        p = _check(bytes(blob))
    except Reject as e:
        return False, None, e.reason
    return True, bytes(blob[:HEAD_LEN]), "ok"


# ---------------------------------------------------------------- honest builder
def honest_input(*, w_t, X, y, t, c, seed, K, batch, lr_fx, B2, nonce, relation=1, delta=None,
                 tree=None):
    """Build an honest blob from numpy dataset arrays (X (n,64) int64, y (n,)) using this module's
    own SGD. Returns (blob, info). `delta` overrides the computed delta (relation 2 or tests)."""
    n_c = len(y)
    root, paths = tree if tree is not None else merkle_root_and_paths(X, y)
    idx = sample_indices(seed, t, c, K, batch, n_c) if relation == 1 else []
    if delta is None:
        wk = run_sgd(w_t, [[X[i] for i in row] for row in idx], [[y[i] for i in row] for row in idx], lr_fx)
        delta = [int(a) - int(b) for a, b in zip(wk, w_t)]
    openings = [(i, [int(v) for v in X[i]], int(y[i]), paths[i]) for i in unique_in_order(idx)]
    kk, bb = (K, batch) if relation == 1 else (0, 0)
    blob = build_input(relation=relation, t=t, c=c, n_c=n_c, K=kk, batch=bb, seed=seed, lr_fx=lr_fx,
                       B2=B2, h_w=model_hash(w_t), C=commit(delta, nonce), R=root, nonce=nonce,
                       w_t=w_t, delta=delta, openings=openings)
    return blob, dict(delta=delta, root=root, idx=idx, n_c=n_c)
