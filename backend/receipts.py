"""Replay-only ZK receipts. Receipt files are read, hashed and verified with zk.bridge.cli.verify_receipt
(verify only; no prover, no proving, no lock needed). `replayed` is always true."""
import datetime as dt
import hashlib
import json
import struct
import threading
import time

from fastapi import HTTPException

from . import hardware
from .common import RES, ROOT, read_csv, rel

ZKDIR = RES / "zk"
SRC = ["demo/results/zk/", "demo/results/zk_bench.md", "docs/zk_cost.md"]
_cache = {}
_mu = threading.Lock()
_expected = None


def expected_publics():
    """{(round, client): 146-byte expected journal} rebuilt from trusted run configuration exactly as
    demo.run_demo.zk_stage / experiments.run_phase3 do (verification inputs only; no proving)."""
    global _expected
    if _expected is not None:
        return _expected
    import numpy as np

    from experiments.run_phase3 import merged
    from fl import aggregate, client, data, model
    from fl import fixedpoint as fx
    from fl import zk_reference as zr
    from fl.merkle import MerkleTree
    from pq import envelope as ev
    from pq import zkpolicy
    p3, cfg = merged("configs/phase3.yaml")
    fr = p3["fl_run"]
    seed, K, batch = fr["seed"], cfg["fl"]["K"], cfg["fl"]["batch"]
    clients, _ = data.load(seed, cfg["clients"])
    trees = [MerkleTree(d.X, d.y) for d in clients]
    lr_fx = int(fx.to_fx(cfg["fl"]["lr"]))
    B2 = fx.bound_sq(cfg["norm_bound_B"])
    w = model.init(seed)
    out = {}
    for t in range(fr["rounds"]):
        deltas = []
        for c in fr["honest"]:
            idx = client.sample_indices(seed, t, c, K, batch, len(clients[c]))
            d = client.local_train(w, clients[c], idx, lr_fx)
            nonce = ev.make_nonce(seed, t, c)
            out[(t, c)] = zkpolicy.expected_public(1, t, c, len(clients[c]), K, batch, seed, lr_fx, B2,
                                                   zr.model_hash(w), zr.commit([int(v) for v in d], nonce), trees[c].root)
            deltas.append(d)
        w = fx.check(w + aggregate.fedavg(deltas))      # the attacker's update is never admitted (see phase3_fl.csv)
    _expected = out
    return out


def _journal_ids(journal):
    if len(journal) >= 14 and journal[:4] == b"QSZK":
        t, c = struct.unpack_from("<II", journal, 6)
        return t, c
    return None, None


def _verify(path, receipt, t, c):
    """-> (verified|None, verify_s|None, verify_error|None). Never guesses true."""
    from zk.bridge import cli
    try:
        exp = expected_publics().get((t, c))
    except Exception as e:  # noqa: BLE001
        return None, None, f"cannot build the expected public journal: {type(e).__name__}: {e}"
    if exp is None:
        return None, None, "no expected public journal for this (round, client) in configs/phase3.yaml"
    t0 = time.perf_counter()
    ok, why = cli.verify_receipt(receipt, exp)
    dtime = time.perf_counter() - t0
    if why in ("binary_missing", "timeout"):
        return None, None, f"verifier unavailable: {why}"
    return bool(ok), round(dtime, 3), None if ok else why


def _p3_rows():
    _, rows = read_csv(RES / "phase3_fl.csv")
    return {(r["round"], r["client"]): r for r in rows if r.get("role") == "honest"}


def _stats(path, row):
    sj = path.with_suffix(".stats.json")
    if sj.exists():
        s = json.loads(sj.read_text())
        return s.get("prove_s"), s.get("cycles"), (round(s["peak_rss_kb"] / 1024) if s.get("peak_rss_kb") else None)
    if row:
        return row.get("prove_s"), row.get("cycles"), row.get("peak_rss_mb")
    return None, None, None


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


def load_receipts():
    if not ZKDIR.exists():
        raise HTTPException(404, "demo/results/zk not found")
    hw = hardware.parse()
    p3 = _p3_rows()
    items = []
    for path in sorted(ZKDIR.glob("r*_c*.receipt")):
        data = path.read_bytes()
        rid = hashlib.sha256(data).hexdigest()[:12]
        jp = path.with_suffix(".journal")
        journal = jp.read_bytes() if jp.exists() else b""
        t, c = _journal_ids(journal)
        with _mu:
            if rid not in _cache:
                _cache[rid] = _verify(path, data, t, c) if t is not None else (None, None, "no journal file: expected public unknown")
            verified, vs, verr = _cache[rid]
        prove_s, cycles, rss = _stats(path, p3.get((t, c)))
        gen = _iso(path.stat().st_mtime)
        hwtxt = ", ".join(x for x in (hw["cpu"], f"{hw['threads']} threads" if hw["threads"] else None, hw["ram"]) if x)
        image_id = None
        if verified:
            try:
                from zk.bridge import cli
                image_id = cli.image_id()
            except Exception:  # noqa: BLE001
                image_id = None
        items.append(dict(id=rid, path=rel(path), bytes=len(data), generated=gen, journal_bytes=len(journal),
                          round=t, client=c, image_id=image_id, prove_s=prove_s, cycles=cycles, peak_rss_mb=rss,
                          verified=verified, verify_s=vs, verify_error=verr, replayed=True,
                          label=f"replayed from receipt {rid}, generated {gen[:10]} (file mtime), on {hwtxt}"))
    return dict(source=SRC, hardware=hw, receipts=items)


def zk_rounds():
    """Per (round, client) proof status from phase3_fl.csv + zk_consensus.csv, joined with receipt verification."""
    rec = {(r["round"], r["client"]): r for r in load_receipts()["receipts"]}
    _, p3 = read_csv(RES / "phase3_fl.csv")
    _, zc = read_csv(RES / "zk_consensus.csv")
    zc_by = {r["round"]: r for r in zc}
    out = []
    for r in p3:
        if r["role"] == "aggregate":
            continue
        key = (r["round"], r["client"])
        rc = rec.get(key)
        z = zc_by.get(r["round"], {})
        if rc is None:
            status, reason, rid, label = "no_receipt", r["reason"], None, "replayed from stored results (no receipt file for this update)"
        elif rc["verified"] is True:
            status, reason, rid, label = "verified", "ok", rc["id"], rc["label"]
        elif rc["verified"] is False:
            status, reason, rid, label = "rejected", rc["verify_error"], rc["id"], rc["label"]
        else:
            status, reason, rid, label = "unverified", rc["verify_error"], rc["id"], rc["label"]
        out.append(dict(round=r["round"], client=r["client"], role=r["role"], status=status, reason=reason,
                        receipt_id=rid, label=label, replayed=True,
                        consensus_accuracy=z.get("accuracy"), consensus_model_hash=z.get("model_hash")))
    return dict(source=["demo/results/phase3_fl.csv", "demo/results/zk_consensus.csv"] + SRC, rounds=out)
