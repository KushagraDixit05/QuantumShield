"""Phase 3 FL integration.  python -m experiments.run_phase3 --config configs/phase3.yaml

Honest clients prove their update with a real RISC Zero receipt, send a v2 signed envelope (proof_hash)
plus the receipt, and the aggregator admits it only after envelope + proof checks. An attacker submits its
update x50 and cannot satisfy the relation (the guest fails). The aggregated model after each round is
compared byte for byte (model hash) with the same participants run through the non-ZK pipeline
(fl.client.local_train + fl.aggregate.fedavg, as in Phase 1/2).
Only (round, client) pairs listed in fl_run take part: proving all 5 clients x 10 rounds would take hours.
"""
import argparse
import csv
import logging
import time

import numpy as np

from attacks import poison
from fl import aggregate, client, data, model
from fl import fixedpoint as fx
from fl import zk_reference as zr
from fl.merkle import MerkleTree
from fl.simulate import ROOT, load_cfg
from pq import envelope as ev
from pq import session as pqsession
from pq import zkpolicy
from zk.bridge import cli


def merged(path):
    p3 = load_cfg(path)
    cfg = load_cfg(p3["base"])
    cfg["fl"] = {**cfg["fl"], **p3.get("fl", {})}
    cfg["norm_bound_B"] = p3.get("norm_bound_B", cfg.get("norm_bound_B"))
    cfg["signatures"] = p3.get("signatures", cfg.get("signatures", "hybrid"))
    return p3, cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/phase3.yaml")
    a = ap.parse_args()
    logging.disable(logging.WARNING)
    p3, cfg = merged(a.config)
    zc, fr = p3["zk"], p3["fl_run"]
    seed, K, batch = fr["seed"], cfg["fl"]["K"], cfg["fl"]["batch"]
    lr_fx = int(fx.to_fx(cfg["fl"]["lr"]))
    B2 = fx.bound_sq(cfg["norm_bound_B"])
    clients, test = data.load(seed, cfg["clients"])
    trees = [MerkleTree(ds.X, ds.y) for ds in clients]
    honest, atk = fr["honest"], fr["attacker"]
    zkp = zkpolicy.ZkPolicy(cli.verify_receipt, [len(ds) for ds in clients], K, batch, seed, lr_fx, B2,
                              roots=[t.root for t in trees])
    mode = p3["signatures"]
    sess = pqsession.Session(mode, cfg.get("sig_alg", "ML-DSA-65"), cfg.get("classical_alg", "Ed25519"),
                             cfg["clients"], cfg["aggregators"], seed, cfg.get("epoch_rounds", 5),
                             [t.root for t in trees], zk=zkp)
    out_dir = ROOT / zc["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    w = model.init(seed)
    w_ref = w.copy()
    rows, t_all = [], time.time()
    print(f"image_id={cli.image_id()} K={K} batch={batch} B={cfg['norm_bound_B']} honest={honest} attacker={atk}")
    for t in range(fr["rounds"]):
        sess.begin_round(t, w)
        deltas, admitted = [], []
        for c in honest:
            nonce = sess.nonce(t, c)
            rec = out_dir / f"r{t}_c{c}.receipt"
            res = cli.client_prove(w, clients[c], t, c, seed, K, batch, lr_fx, B2, nonce, trees[c],
                                   rec, out_dir / f"r{t}_c{c}.journal", po2=zc["po2"], kind=zc["receipt_kind"])
            rb = rec.read_bytes()
            env = sess.client_envelope(t, c, res["delta"], rb)
            t0 = time.time()
            ok = sess.admit(t, c, env, res["delta"], rb)
            vs = time.time() - t0
            st = res["stats"]
            rows.append(dict(round=t, client=c, role="honest", admitted=ok, reason="ok" if ok else sess.drop_log[-1][2],
                             prove_s=st["prove_s"], aggregator_check_s=round(vs, 3), receipt_bytes=st["receipt_bytes"],
                             cycles=st["cycles"], peak_rss_mb=round(st["peak_rss_kb"] / 1024), delta_norm=round(float(np.sqrt(fx.norm_sq(res["delta"]))) / fx.ONE, 4)))
            print(rows[-1], flush=True)
            if ok:
                deltas.append(res["delta"])
                admitted.append(c)
        # attacker: scaled update. The guest cannot be satisfied, so there is no receipt.
        idx = client.sample_indices(seed, t, atk, K, batch, len(clients[atk]))
        d_bad = poison.scaled(client.local_train(w, clients[atk], idx, lr_fx), fr["attack_scale"])
        blob, info = zr.honest_input(w_t=w, X=clients[atk].X, y=clients[atk].y, t=t, c=atk, seed=seed, K=K, batch=batch,
                                     lr_fx=lr_fx, B2=B2, nonce=sess.nonce(t, atk), delta=d_bad, tree=None)
        proves, _, st = cli.execute(blob)
        env = sess.client_envelope(t, atk, d_bad)                      # v1 envelope: no proof_hash
        ok = sess.admit(t, atk, env, d_bad, None)
        rows.append(dict(round=t, client=atk, role=f"attacker x{fr['attack_scale']}", admitted=ok,
                         reason=f"guest_can_prove={proves}; " + (sess.drop_log[-1][2] if not ok else "ok"),
                         norm_sq_over_B2=round(fx.norm_sq(d_bad) / B2, 1)))
        print(rows[-1], flush=True)
        if ok:
            deltas.append(d_bad)
            admitted.append(atk)
        w = fx.check(w + aggregate.fedavg(deltas))
        # reference: same participants, non-ZK pipeline
        refd = []
        for c in honest:
            ix = client.sample_indices(seed, t, c, K, batch, len(clients[c]))
            refd.append(client.local_train(w_ref, clients[c], ix, lr_fx))
        w_ref = fx.check(w_ref + aggregate.fedavg(refd))
        same = ev.model_hash(w) == ev.model_hash(w_ref)
        acc = model.accuracy(w, test)
        rows.append(dict(round=t, client="agg", role="aggregate", admitted=admitted, reason=f"model_hash_equal_to_non_zk={same}",
                         accuracy=round(acc, 4)))
        print(rows[-1], flush=True)
        assert same, "ZK pipeline diverged from the non-ZK pipeline"
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("round", "client", "role"), k))
    with open(ROOT / (fr["out_prefix"] + ".csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows)
    print(f"done in {time.time() - t_all:.0f}s -> {fr['out_prefix']}.csv")


if __name__ == "__main__":
    main()
