"""Seeded test-vector generator for the Phase 3 relation.

python -m zk.bridge.vectors --config configs/phase3.yaml --out zk/bridge/vectors/

Writes <name>.in.bin and <name>.expect.json per vector. The expectation (ok, reason, journal) comes
from the independent reference fl/zk_reference.py; the generator also asserts that every vector's
reference verdict equals the verdict the vector was designed for. Deterministic: same config, same bytes.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fl import data, model  # noqa: E402
from fl import fixedpoint as fx  # noqa: E402
from fl import zk_reference as zr  # noqa: E402


def load_config(path):
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    cfg = yaml.safe_load(p.read_text())
    if "base" in cfg:
        base = load_config(cfg.pop("base"))
        base.update(cfg)
        cfg = base
    return cfg


class Gen:
    def __init__(self, cfg):
        self.cfg = cfg
        self.seed = int(cfg.get("seeds", [cfg.get("seed", 0)])[0])
        self.K, self.batch = cfg["fl"]["K"], cfg["fl"]["batch"]
        self.lr_fx = int(fx.to_fx(cfg["fl"]["lr"]))
        self.B2 = fx.bound_sq(cfg["norm_bound_B"])  # config handling only; the relation uses the integer
        self.relation = cfg.get("zk", {}).get("relation", 1)
        self.vectors = {}  # name -> (blob, intended_ok, meta)
        self._ds = {}

    # -------------------------------------------------------------- data
    def client(self, seed, c, n=None):
        if seed not in self._ds:
            self._ds[seed] = data.load(seed, self.cfg["clients"])[0]
        ds = self._ds[seed][c]
        X, y = ds.X, ds.y
        if n is not None:
            X, y = X[:n], y[:n]
        return X, y

    def model_at(self, seed, t):
        w = model.init(seed).astype(np.int64)
        if t:
            noise = np.random.default_rng(seed * 1000 + t).integers(-2000, 2000, w.shape)
            w = w + noise
        return [int(v) for v in w]

    def nonce(self, seed, t, c, tag=0):
        return zr._sha(b"QSFL-vec" + seed.to_bytes(8, "little") + bytes([t % 256, c % 256, tag]))

    # -------------------------------------------------------------- parts
    def parts(self, *, seed=None, t=0, c=0, K=None, batch=None, n=None, lr_fx=None, B2=None, relation=1,
              w_t=None, X=None, y=None, delta=None, tag=0):
        """Honest keyword set for zr.build_input (+ extras under key '_')."""
        seed = self.seed if seed is None else seed
        K = self.K if K is None else K
        batch = self.batch if batch is None else batch
        lr_fx = self.lr_fx if lr_fx is None else lr_fx
        if X is None:
            X, y = self.client(seed, c, n)
        w_t = self.model_at(seed, t) if w_t is None else w_t
        nonce = self.nonce(seed, t, c, tag)
        n_c = len(y)
        root, paths = zr.merkle_root_and_paths(X, y)
        idx = zr.sample_indices(seed, t, c, K, batch, n_c)
        if delta is None:
            try:
                wk = zr.run_sgd(w_t, [[X[i] for i in r] for r in idx], [[y[i] for i in r] for r in idx], lr_fx)
                delta = [int(a) - int(b) for a, b in zip(wk, w_t)]
            except zr.Reject:  # no honest delta exists (guard/overflow/label vectors): use zeros
                delta = [0] * model.N_PARAMS
        if B2 is None:
            B2 = max(self.B2, sum(v * v for v in delta)) if relation == 1 else self.B2
        openings = [(i, [int(v) for v in X[i]], int(y[i]), list(paths[i])) for i in zr.unique_in_order(idx)]
        P = dict(relation=relation, t=t, c=c, n_c=n_c, K=K if relation == 1 else 0,
                 batch=batch if relation == 1 else 0, seed=seed, lr_fx=lr_fx, B2=B2,
                 h_w=zr.model_hash(w_t), C=zr.commit(delta, nonce), R=root, nonce=nonce,
                 w_t=w_t if relation == 1 else None, delta=delta, openings=openings if relation == 1 else [])
        return P

    def recommit(self, P):
        P["C"] = zr.commit(P["delta"], P["nonce"])
        return P

    def add(self, name, P_or_blob, ok, reason=None):
        """Register a vector. Asserts the reference verdict equals the designed one."""
        blob = P_or_blob if isinstance(P_or_blob, bytes) else zr.build_input(**P_or_blob)
        got_ok, jr, got_reason = zr.evaluate(blob)
        assert got_ok == ok, f"{name}: designed ok={ok}, reference says {got_ok} ({got_reason})"
        if reason is not None:
            assert got_reason == reason, f"{name}: designed {reason}, reference says {got_reason}"
        rel = blob[5] if len(blob) > 5 else None
        K, batch = (int.from_bytes(blob[18:22], "little"), int.from_bytes(blob[22:26], "little")) if len(blob) >= 26 else (None, None)
        self.vectors[name] = (blob, dict(ok=got_ok, reason=got_reason,
                                         journal_hex=jr.hex() if jr else None, relation=rel, K=K, batch=batch))

    # -------------------------------------------------------------- the list
    def build(self):
        A = self.add
        P = self.parts
        # honest config K/batch (real-proof candidates), different seeds/rounds/clients
        for seed, t, c in [(0, 0, 0), (0, 0, 1), (0, 1, 2), (0, 3, 3), (0, 9, 4), (1, 2, 0), (2, 5, 1), (0, 4, 2)]:
            A(f"honest_main_s{seed}_t{t}_c{c}", P(seed=seed, t=t, c=c, B2=self.B2), True, "ok")
        A("honest_cfg", P(B2=self.B2), True, "ok")
        A("honest_k1b1", P(K=1, batch=1, c=1), True, "ok")
        A("honest_k3b2", P(K=3, batch=2, c=2, t=1), True, "ok")
        A("honest_k1b32", P(K=1, batch=32, c=3), True, "ok")
        A("honest_k2b8", P(K=2, batch=8, c=4, t=2), True, "ok")
        # dataset sizes: odd, even, one; many repeated indices
        for n in (1, 2, 3, 4, 5, 7, 9, 16):
            A(f"honest_nc{n}_k2b4", P(K=2, batch=4, n=n), True, "ok")
        A("honest_nc1_k1b1", P(K=1, batch=1, n=1), True, "ok")
        A("repeated_idx_nc2_k3b8", P(K=3, batch=8, n=2, c=1), True, "ok")
        A("repeated_idx_nc3_k4b4", P(K=4, batch=4, n=3, c=2), True, "ok")
        # relation 2
        h = P()
        A("rel2_honest_delta", P(relation=2, delta=h["delta"], B2=max(self.B2, sum(v * v for v in h["delta"]))), True, "ok")
        small = [i % 7 - 3 for i in range(model.N_PARAMS)]
        n2 = sum(v * v for v in small)
        A("rel2_small", P(relation=2, delta=small, B2=n2 + 5), True, "ok")
        A("rel2_norm_exact_accept", P(relation=2, delta=small, B2=n2), True, "ok")
        A("rel2_norm_plus1_reject", P(relation=2, delta=small, B2=n2 - 1), False, "norm_exceeded")
        cap = [0] * model.N_PARAMS
        cap[7] = (1 << 25) - 1
        A("rel2_entry_below_cap_accept", P(relation=2, delta=cap, B2=(1 << 50) - 1), True, "ok")
        cap2 = list(cap); cap2[7] = 1 << 25
        A("rel2_entry_at_cap_reject", P(relation=2, delta=cap2, B2=(1 << 50) - 1), False, "norm_entry_cap")
        cap3 = list(cap); cap3[7] = -(1 << 25)
        A("rel2_entry_neg_cap_reject", P(relation=2, delta=cap3, B2=(1 << 50) - 1), False, "norm_entry_cap")
        cap4 = list(cap); cap4[7] = -((1 << 25) - 1)
        A("rel2_entry_neg_below_cap_accept", P(relation=2, delta=cap4, B2=(1 << 50) - 1), True, "ok")
        p = P(relation=2, delta=small, B2=n2 + 5)
        A("rel2_trailing_byte", zr.build_input(**p) + b"\0", False, "trailing_bytes")
        p = P(relation=2, delta=small, B2=n2 + 5); p["K"] = 2
        A("rel2_K_nonzero", p, False, "bad_params")
        p = P(relation=2, delta=small, B2=n2 + 5); p["batch"] = 4
        A("rel2_batch_nonzero", p, False, "bad_params")
        p = P(relation=2, delta=small, B2=n2 + 5); self.recommit(p); p["C"] = bytes(32)
        A("rel2_bad_commitment", p, False, "commitment_mismatch")
        # norm in relation 1: exactly B2 accept, norm = B2+1 reject
        h = P(c=2)
        nn = sum(v * v for v in h["delta"])
        p = copy.deepcopy(h); p["B2"] = nn
        A("norm_exact_B2_accept", p, True, "ok")
        p = copy.deepcopy(h); p["B2"] = nn - 1
        A("norm_B2_plus1_reject", p, False, "norm_exceeded")
        # B2 >= 2^50, lr, parameter checks
        for nm, v in (("b2_2pow50", 1 << 50), ("b2_max", (1 << 64) - 1)):
            p = P(); p["B2"] = v
            A(nm + "_reject", p, False, "b2_too_large")
        p = P(); p["B2"] = (1 << 50) - 1
        A("b2_2pow50_minus1_accept", p, True, "ok")
        p = P(); p["lr_fx"] = 0
        A("lr_zero", p, False, "bad_lr")
        p = P(); p["lr_fx"] = -5
        A("lr_negative", p, False, "bad_lr")
        p = P(); p["n_c"] = 0
        A("nc_zero", p, False, "bad_n_c")
        p = P(); p["K"] = 0
        A("K_zero", p, False, "bad_K")
        p = P(); p["batch"] = 3
        A("batch_not_pow2", p, False, "bad_batch")
        p = P(); p["batch"] = 0
        A("batch_zero", p, False, "bad_batch")
        p = P(); p["relation"] = 3
        A("relation_3", p, False, "bad_relation")
        p = P(); p["version"] = 2
        A("bad_version", p, False, "bad_version")
        p = P(); p["magic"] = b"QSZX"
        A("bad_magic", p, False, "bad_magic")
        blob = zr.build_input(**P())
        A("trailing_byte", blob + b"\0", False, "trailing_bytes")
        A("truncated_one_byte", blob[:-1], False, "truncated")
        A("empty_blob", b"", False, "truncated")
        # commitment / hash / delta
        p = P(); p["C"] = bytes([p["C"][0] ^ 1]) + p["C"][1:]
        A("wrong_commitment", p, False, "commitment_mismatch")
        p = P(); p["nonce"] = bytes(32)
        A("wrong_nonce", p, False, "commitment_mismatch")
        p = P(); p["h_w"] = bytes([p["h_w"][0] ^ 1]) + p["h_w"][1:]
        A("wrong_model_hash", p, False, "model_hash_mismatch")
        p = P(); p["delta"][5] += 1; self.recommit(p)
        A("wrong_delta_plus1_recommitted", p, False, "delta_mismatch")
        p = P(); p["delta"][2409] -= 1; self.recommit(p)
        A("wrong_delta_minus1_last_recommitted", p, False, "delta_mismatch")
        p = P(); p["delta"][5] += 1
        A("wrong_delta_plus1_stale_commitment", p, False, "commitment_mismatch")
        p = P(); p["w_t"][-1] += 1 << 15; p["h_w"] = zr.model_hash(p["w_t"])
        A("wrong_wt_consistent_hash_stale_delta", p, False, None)
        # merkle
        p = P(c=1)
        o = list(p["openings"][0]); o[3] = list(o[3]); o[3][0] = bytes([o[3][0][0] ^ 1]) + o[3][0][1:]
        p["openings"][0] = tuple(o)
        A("merkle_flipped_sibling_bit", p, False, "bad_merkle_path")
        p = P(c=1)
        o = list(p["openings"][-1]); o[3] = list(o[3]); o[3][-1] = bytes([o[3][-1][0] ^ 0x80]) + o[3][-1][1:]
        p["openings"][-1] = tuple(o)
        A("merkle_flipped_top_sibling_bit", p, False, "bad_merkle_path")
        p = P(c=1)
        o = list(p["openings"][-1]); o[3] = o[3] + [bytes(32)]; p["openings"][-1] = tuple(o)
        A("merkle_path_too_long_last", p, False, "trailing_bytes")
        p = P(c=1)
        o = list(p["openings"][0]); o[3] = o[3] + [bytes(32)]; p["openings"][0] = tuple(o)
        A("merkle_path_too_long_first", p, False, None)
        p = P(c=1)
        o = list(p["openings"][-1]); o[3] = o[3][:-1]; p["openings"][-1] = tuple(o)
        A("merkle_path_too_short_last", p, False, "truncated")
        p = P(c=1)
        o = list(p["openings"][0]); x = list(o[1]); x[0] += 1; o[1] = x; p["openings"][0] = tuple(o)
        A("merkle_wrong_leaf_data", p, False, "bad_merkle_path")
        p = P(c=1)
        o = list(p["openings"][0]); o[2] = (o[2] + 1) % 10; p["openings"][0] = tuple(o)
        A("merkle_wrong_label", p, False, "bad_merkle_path")
        p = P(c=1); p["R"] = bytes(32)
        A("merkle_wrong_root", p, False, "bad_merkle_path")
        p = P(c=1); p["openings"].reverse()
        A("openings_reversed", p, False, "opening_index_mismatch")
        p = P(c=1); p["openings"][0], p["openings"][1] = p["openings"][1], p["openings"][0]
        A("openings_first_two_swapped", p, False, "opening_index_mismatch")
        p = P(c=1); p["openings"] = p["openings"][:-1]
        A("opening_missing", p, False, "bad_opening_count")
        p = P(c=1); p["openings"] = p["openings"] + [p["openings"][0]]
        A("opening_duplicate_extra", p, False, "bad_opening_count")
        p = P(c=1); p["openings"] = []
        A("openings_none", p, False, "bad_opening_count")
        p = P(c=1); p["n_open"] = 0xFFFFFFFF
        A("n_open_huge", p, False, "truncated")
        p = P(c=1); p["n_c"] += 1
        A("n_c_claimed_larger", p, False, None)
        p = P(c=1); o = list(p["openings"][0]); o[0] = p["n_c"]; p["openings"][0] = tuple(o)
        A("opening_index_out_of_range", p, False, "opening_index_mismatch")
        # label 10 committed under R
        X, y = self.client(self.seed, 0, 4)
        y = np.array(y); y[:] = 10
        P10 = P(K=1, batch=1, X=X, y=y, delta=[0] * model.N_PARAMS, B2=self.B2)
        A("label_10", P10, False, "label_range")
        # guard boundary: X max 2^16 at column 0, huge W1 entry at column 1 where X is zero
        Xg = np.zeros((1, 64), dtype=np.int64); Xg[0, 0] = 1 << 16
        yg = np.array([3])
        for nm, m, ok in (("guard_below_2pow62", (1 << 40) - 1, True), ("guard_at_2pow62", 1 << 40, False),
                          ("guard_neg_at_2pow62", -(1 << 40), False), ("guard_neg_below", -((1 << 40) - 1), True)):
            w = self.model_at(self.seed, 0); w[1] = m  # W1[0, 1]
            A(nm, P(K=1, batch=1, X=Xg, y=yg, w_t=w, B2=self.B2), ok, "ok" if ok else "guard")
        w = self.model_at(self.seed, 0); w[1] = (1 << 40) - 1
        A("guard_below_cfg", P(X=Xg, y=yg, w_t=w), True, "ok")
        p = P(); p["lr_fx"] = 1 << 50; self.recommit(p)
        A("guard_lr_huge", p, False, "guard")
        w = self.model_at(self.seed, 0); w[0] = (1 << 63) - 1  # W1[0,0] huge, X[0,0] nonzero: guard fires first
        A("guard_w1_i64max", P(K=1, batch=1, X=Xg, y=yg, w_t=w), False, "guard")
        # checked add overflow without the guard firing: b1[0] = i64 max, positive product
        w = self.model_at(self.seed, 0); w[2048] = (1 << 63) - 1; w[0] = 1 << 16  # b1[0]; W1[0,0]=1
        Xo = np.zeros((1, 64), dtype=np.int64); Xo[0, 0] = 1 << 16
        A("overflow_checked_add", P(K=1, batch=1, X=Xo, y=yg, w_t=w, delta=[0] * model.N_PARAMS, B2=self.B2),
          False, "overflow")
        # norm over bound for honest delta
        p = P(); p["B2"] = 1000
        A("norm_over_small_B2", p, False, "norm_exceeded")
        return self


def write_all(g, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("*.in.bin")) + list(out.glob("*.expect.json")):
        old.unlink()
    for name, (blob, meta) in sorted(g.vectors.items()):
        (out / f"{name}.in.bin").write_bytes(blob)
        (out / f"{name}.expect.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")


def generate(config="configs/phase3.yaml"):
    return Gen(load_config(config)).build()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/phase3.yaml")
    ap.add_argument("--out", default=str(ROOT / "zk/bridge/vectors"))
    a = ap.parse_args(argv)
    g = generate(a.config)
    write_all(g, a.out)
    acc = sum(m["ok"] for _, m in g.vectors.values())
    print(f"{len(g.vectors)} vectors ({acc} accept, {len(g.vectors) - acc} reject) -> {a.out}")


if __name__ == "__main__":
    main()
