"""Reference (fl/zk_reference.py) vs the Phase 1 code, vector expectations, determinism. No proving."""
import json
import struct

import numpy as np
import pytest

from fl import client as flc
from fl import data, model
from fl import fixedpoint as fx
from fl import merkle
from fl import zk_reference as zr
from pq import zkpolicy
from zk.bridge import vectors as V

CFG = "configs/phase3.yaml"


@pytest.fixture(scope="module")
def gen():
    return V.generate(CFG)


def _vec(gen, name):
    return gen.vectors[name][0]


# ------------------------------------------------------------------ SGD cross-check
@pytest.mark.parametrize("seed", range(12))
def test_run_sgd_matches_local_train(seed):
    rng = np.random.default_rng(seed)
    clients, _ = data.load(seed, 5)
    ds = clients[seed % 5]
    K, batch = [(1, 1), (2, 4), (3, 2), (1, 32), (2, 8), (4, 4)][seed % 6]
    t, c = int(rng.integers(0, 10)), seed % 5
    w0 = model.init(seed) + rng.integers(-5000, 5000, model.N_PARAMS)
    lr = int(fx.to_fx(0.1 + 0.05 * seed))
    idx = flc.sample_indices(seed, t, c, K, batch, len(ds))
    assert zr.sample_indices(seed, t, c, K, batch, len(ds)) == idx.tolist()
    want = flc.local_train(w0, ds, idx, lr)
    wk = zr.run_sgd([int(v) for v in w0], [[ds.X[i] for i in r] for r in idx],
                    [[ds.y[i] for i in r] for r in idx], lr)
    assert [int(a) - int(b) for a, b in zip(wk, w0)] == want.tolist()


def test_guard_where_reference_raises_but_local_train_does_not():
    """Documented divergence: fixedpoint._maxabs uses np.abs, which maps int64 min to itself (negative),
    so the Phase 1 guard passes and the product wraps. The reference works on Python ints and raises."""
    clients, _ = data.load(0, 5)
    ds = clients[0]
    w0 = model.init(0).copy()
    w0[1] = np.iinfo(np.int64).min
    idx = flc.sample_indices(0, 0, 0, 1, 1, len(ds))
    flc.local_train(w0, ds, idx, 1000)  # does not raise (wraps silently)
    with pytest.raises(zr.Reject) as e:
        zr.run_sgd([int(v) for v in w0], [[ds.X[i] for i in r] for r in idx],
                   [[ds.y[i] for i in r] for r in idx], 1000)
    assert e.value.reason == "guard"


def test_checked_add_raises_where_numpy_wraps():
    with pytest.raises(zr.Reject) as e:
        zr.add([(1 << 63) - 1], [1])
    assert e.value.reason == "overflow"
    with pytest.raises(zr.Reject):
        zr.sub([-(1 << 63)], [1])


def test_floor_shift_on_negative_numbers():
    # (A @ B) >> 16 floors toward -inf
    A = [[-1, 0], [1, 0], [-65536, 0], [-65537, 0]]
    B = [[1, 0], [0, 0]]
    got = zr.sum_prod_shift(A, B)[:, 0].tolist()
    assert got == [-1, 0, -1, -2]
    assert got == (np.array(A, dtype=np.int64) @ np.array(B, dtype=np.int64) >> 16)[:, 0].tolist()
    assert zr.fx_mul([-3], [1]).tolist() == [-1]
    assert zr.fx_mul([3], [-65536]).tolist() == [-3]


def test_guard_rule_boundary():
    # exact: 2^31 * 2^30 * 2 = 2^62 -> fail; (2^31-1)*2^30*2 -> pass
    A = np.array([[1 << 31, 0]], dtype=object); B = np.array([[1 << 30], [0]], dtype=object)
    with pytest.raises(zr.Reject):
        zr.sum_prod_shift(A, B)
    A = np.array([[(1 << 31) - 1, 0]], dtype=object)
    assert zr.sum_prod_shift(A, B).shape == (1, 1)
    with pytest.raises(zr.Reject):
        zr.fx_mul([1 << 31], [1 << 31])
    assert zr.fx_mul([(1 << 31) - 1], [1 << 31]).shape == (1,)


# ------------------------------------------------------------------ merkle / hashes
def test_merkle_matches_fl_merkle_and_is_strict():
    for n in (1, 2, 3, 5, 8, 9):
        clients, _ = data.load(0, 5)
        X, y = clients[0].X[:n], clients[0].y[:n]
        tree = merkle.MerkleTree(X, y)
        root, paths = zr.merkle_root_and_paths(X, y)
        assert root == tree.root
        for i in range(n):
            assert paths[i] == tree.path(i)
            assert zr.merkle_check(root, n, i, X[i], y[i], paths[i])
            assert not zr.merkle_check(root, n, i, X[i], y[i], paths[i] + [bytes(32)])
            if paths[i]:
                assert not zr.merkle_check(root, n, i, X[i], y[i], paths[i][:-1])
        assert not zr.merkle_check(root, n, n, X[0], y[0], paths[0])


# ------------------------------------------------------------------ input blob
def test_input_round_trip(gen):
    blob = _vec(gen, "honest_main_s0_t0_c0")
    p = zr.parse_input(blob)
    assert (p["relation"], p["t"], p["c"], p["K"], p["batch"]) == (1, 0, 0, 4, 8)
    again = zr.build_input(**{k: p[k] for k in ("relation", "t", "c", "n_c", "K", "batch", "seed", "lr_fx", "B2",
                                                "h_w", "C", "R", "nonce", "w_t", "delta", "openings")})
    assert again == blob
    assert len(blob) == 178 + 2 * 19280 + 4 + len(p["openings"]) * (4 + 512 + 4 + 32 * zr.depth(p["n_c"]))


def test_matches_lead_probe_builder():
    """zk/probe/make_input.py (lead) builds the same bytes for the same situation, except for the
    nonce and B2 choices which we pass through."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("probe_make_input", Path(__file__).resolve().parents[2] / "probe" / "make_input.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    lead, info = mod.build(4, 8)
    p = zr.parse_input(lead)
    mine = zr.build_input(**{k: p[k] for k in ("relation", "t", "c", "n_c", "K", "batch", "seed", "lr_fx", "B2",
                                               "h_w", "C", "R", "nonce", "w_t", "delta", "openings")})
    assert mine == lead
    ok, j, why = zr.evaluate(lead)
    assert ok and j == lead[:146], why


# ------------------------------------------------------------------ vectors
def test_vector_count_and_k2b4_honest(gen):
    assert len(gen.vectors) >= 40
    k2 = [n for n, (b, m) in gen.vectors.items() if n.startswith("honest_main_s") and m["ok"]]
    assert len(k2) >= 4


def test_every_vector_matches_its_expectation(gen):
    for name, (blob, meta) in gen.vectors.items():
        ok, j, why = zr.evaluate(blob)
        assert (ok, why) == (meta["ok"], meta["reason"]), name
        assert (j.hex() if j else None) == meta["journal_hex"], name
        assert ok == (why == "ok")


def test_reject_vectors_have_designed_reasons(gen):
    want = {
        "wrong_commitment": "commitment_mismatch", "wrong_model_hash": "model_hash_mismatch",
        "wrong_delta_plus1_recommitted": "delta_mismatch", "merkle_flipped_sibling_bit": "bad_merkle_path",
        "merkle_path_too_long_last": "trailing_bytes", "openings_reversed": "opening_index_mismatch",
        "label_10": "label_range", "trailing_byte": "trailing_bytes", "bad_magic": "bad_magic",
        "b2_2pow50_reject": "b2_too_large", "norm_B2_plus1_reject": "norm_exceeded",
        "guard_at_2pow62": "guard", "overflow_checked_add": "overflow", "rel2_entry_at_cap_reject": "norm_entry_cap",
    }
    for n, r in want.items():
        assert gen.vectors[n][1]["reason"] == r, n
    assert gen.vectors["norm_exact_B2_accept"][1]["ok"]
    assert gen.vectors["guard_below_2pow62"][1]["ok"]


def test_journal_equals_pq_expected_public(gen):
    n_checked = 0
    for name, (blob, meta) in gen.vectors.items():
        if not meta["ok"]:
            continue
        p = zr.parse_input(blob)
        exp = zkpolicy.expected_public(p["relation"], p["t"], p["c"], p["n_c"], p["K"], p["batch"], p["seed"],
                                       p["lr_fx"], p["B2"], p["h_w"], p["C"], p["R"])
        assert bytes.fromhex(meta["journal_hex"]) == exp, name
        assert exp == zr.journal_for(**{k: p[k] for k in ("relation", "t", "c", "n_c", "K", "batch", "seed", "lr_fx",
                                                          "B2", "h_w", "C", "R")})
        assert len(exp) == 146
        n_checked += 1
    assert n_checked >= 30


def test_vector_generation_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    V.write_all(V.generate(CFG), a)
    V.write_all(V.generate(CFG), b)
    fa = sorted(p.name for p in a.iterdir())
    assert fa == sorted(p.name for p in b.iterdir()) and len(fa) >= 80
    for n in fa:
        assert (a / n).read_bytes() == (b / n).read_bytes(), n


def test_committed_vectors_in_repo_are_current(gen, tmp_path):
    from pathlib import Path
    d = Path(V.__file__).parent / "vectors"
    if not d.exists():
        pytest.skip("vectors not generated")
    for name, (blob, meta) in gen.vectors.items():
        assert (d / f"{name}.in.bin").read_bytes() == blob, name
        assert json.loads((d / f"{name}.expect.json").read_text()) == meta, name
