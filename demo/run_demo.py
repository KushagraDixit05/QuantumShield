"""End-to-end demo: FL -> signed envelopes -> verification -> 4-node vote consensus -> aggregation.

  python -m demo.run_demo --all
  python -m demo.run_demo --stage scenarios --attack scaled --defence on --seeds 0
  python -m demo.run_demo --stage zk

Stage `scenarios` (configs/demo.yaml -> configs/mvp.yaml: K=20, batch 32, 10 rounds, 5 clients, 1 attacker),
every run through consensus.node.Node (n=4, f=1, quorum 3) on the simulated asyncio network:
  defence off : classical Ed25519 signatures only, plain FedAvg                       (the baseline FL)
  defence on  : hybrid Ed25519 + ML-DSA-65 signatures + norm gate B + FedAvg of what passes
In this stage the norm gate is a PLAINTEXT check of ||delta||^2 <= B^2. It is the relation the ZK proof
enforces, but no proof is generated here (proving 50 updates takes about 5 h). It is not a ZK result.

Stage `zk` (configs/phase3.yaml: K=4, batch 8): the REAL RISC Zero receipts produced in Phase 3
(demo/results/zk/r{t}_c{c}.receipt) go through `consensus.node.zk_check` at every node (real verifier, verify
only, no proving, no dev mode). The attacker's x50 update has no receipt because the guest cannot prove it.
"""
import argparse
import asyncio
import csv
import json
import logging
import time
from collections import Counter
from pathlib import Path

import numpy as np

from attacks import envelope_attacks, poison
from consensus import fault
from consensus.messages import Update
from consensus.node import Network, Node, run_round, run_rounds_with, signature_check, zk_check
from fl import aggregate, client, data, model
from fl import fixedpoint as fx
from fl.merkle import MerkleTree
from fl.simulate import ROOT, load_cfg
from pq import envelope as ev
from pq import policy, votes
from pq import session as pqsession
from pq import zkpolicy

OUT = ROOT / "demo" / "results"
ATTACKS = ["none", "scaled", "forged", "replay"]
N_AGG, F = 4, 1


def norm_gate(verifier, B2):
    """Signature/commitment check, then a plaintext norm gate (stands in for the ZK proof in this stage)."""
    base = signature_check(verifier)

    def check(u):
        ok, reason = base(u)
        if ok and fx.norm_sq(u.delta) > B2:
            return False, "norm_bound_exceeded"
        return ok, reason
    return check


def run_scenario(cfg, attack, defence_on, seed, on_round=None):
    n_cl, mal = cfg["clients"], cfg["malicious_clients"]
    nb = n_cl - mal
    fl = cfg["fl"]
    clients, test = data.load(seed, n_cl)
    B2 = fx.bound_sq(cfg["norm_bound_B"])
    lr_fx = int(fx.to_fx(fl["lr"]))
    mode = "hybrid" if defence_on else "classical"
    pq_alg, cl_alg = cfg.get("sig_alg", "ML-DSA-65"), cfg.get("classical_alg", "Ed25519")
    sess = pqsession.Session(mode, pq_alg, cl_alg, n_cl, N_AGG, seed, cfg.get("epoch_rounds", 5),
                             pqsession.merkle_roots(clients))
    net = Network(N_AGG)
    nodes = []
    for i in range(N_AGG):
        v = policy.Verifier(sess.registry, mode, pq_alg, cl_alg)
        hook = norm_gate(v, B2) if defence_on else signature_check(v)
        nodes.append(Node(i, N_AGG, F, sess.registry, v, net, defence="fedavg", B2=B2, verify_update=hook, seed=seed))
    res = dict(acc=[model.accuracy(model.init(seed), test)], diverged_round=None, latency_ms=[], update_env_bytes=[],
               rejects=Counter(), accepted=[], finalized_rounds=0)
    w = model.init(seed)
    prev = {}

    async def body():
        nonlocal w
        for t in range(cfg["rounds"]):
            sess.begin_round(t, w)
            ups, sent = [], {}
            for c in range(n_cl):
                idx = client.sample_indices(seed, t, c, fl["K"], fl["batch"], len(clients[c]))
                try:
                    d = client.local_train(w, clients[c], idx, lr_fx)
                except fx.FixedPointOverflow:             # the poisoned global model is out of int64 range (D-012)
                    res["diverged_round"] = t
                    res["acc"] += [0.0] * (cfg["rounds"] + 1 - len(res["acc"]))
                    if on_round:
                        on_round(dict(round=t, diverged=True))
                    return
                if c >= nb and attack == "scaled":
                    d = poison.scaled(d, cfg["attack"]["scale"])
                env = sess.client_envelope(t, c, d)
                sent[c] = (env, d)
                if c >= nb and attack == "replay" and c in prev:
                    env, d = prev[c]                      # old envelope resent verbatim
                if c == 0 and attack == "forged":         # victim 0's Ed25519 key only
                    env, d = envelope_attacks.forge_with_classical_key(sess, 0, t, poison.scaled(d, cfg["attack"]["scale"]))
                ups.append(Update(c, env, d))
                res["update_env_bytes"].append(len(env.wire()))
            prev.update(sent)
            t0 = time.perf_counter()
            await run_round(nodes, net, sess.registry, sess.algs, t, w, ups)
            res["latency_ms"].append((time.perf_counter() - t0) * 1000)
            fin = nodes[0].finalized.get(t)
            res["accepted"].append(nodes[0].accepted_ids(t))
            if fin is None:                               # int64 overflow at every node (D-012) or no quorum
                res["diverged_round"] = t
                res["acc"] += [0.0] * (cfg["rounds"] + 1 - len(res["acc"]))
                if on_round:
                    on_round(dict(round=t, diverged=True))
                return
            res["finalized_rounds"] += 1
            w = fin[1]
            res["acc"].append(model.accuracy(w, test))
            if on_round:
                on_round(dict(round=t, accuracy=res["acc"][-1], accepted=res["accepted"][-1], latency_ms=res["latency_ms"][-1],
                              model_hash=fin[0].hex()[:16],
                              drops=[dict(client=c, reason=why) for (r, c, why) in nodes[0].drop_log() if r == t]))

    try:
        asyncio.run(run_rounds_with(nodes, net, body))
    except fx.FixedPointOverflow:
        if res["diverged_round"] is None:
            raise
    for r, c, why in nodes[0].drop_log():
        res["rejects"][(r, c, why)] += 1
    return res


def scenarios(cfg, seeds, attacks, defences):
    OUT.mkdir(parents=True, exist_ok=True)
    rows, rej, curves = [], [], {}
    for atk in attacks:
        for dfn in defences:
            for s in seeds:
                t0 = time.time()
                r = run_scenario(cfg, atk, dfn == "on", s)
                lat = float(np.mean(r["latency_ms"])) if r["latency_ms"] else float("nan")
                rows.append(dict(attack=atk, defence=dfn, seed=s, final_acc=round(r["acc"][-1], 4),
                                 diverged_round="" if r["diverged_round"] is None else r["diverged_round"],
                                 finalized_rounds=r["finalized_rounds"], mean_round_latency_ms=round(lat, 1),
                                 mean_update_env_bytes=round(float(np.mean(r["update_env_bytes"]))) if r["update_env_bytes"] else "",
                                 rejected=sum(r["rejects"].values())))
                for (rd, c, why), k in sorted(r["rejects"].items()):
                    rej.append(dict(attack=atk, defence=dfn, seed=s, round=rd, client=c, reason=why))
                if s == seeds[0]:
                    curves[f"{atk}/{dfn}"] = [round(a, 6) for a in r["acc"]]
                print(f"{atk:7s} defence={dfn:3s} seed={s} final_acc={r['acc'][-1]:.4f} rejected={rows[-1]['rejected']} "
                      f"diverged={rows[-1]['diverged_round'] or '-'} ({time.time() - t0:.0f}s)", flush=True)
    _write(OUT / "scenarios.csv", rows)
    _write(OUT / "rejections.csv", rej)
    sc = {k: curves[f"{a}/{d}"] for k, (a, d) in {"A": ("none", "off"), "B": ("scaled", "off"), "C": ("scaled", "on")}.items()
          if f"{a}/{d}" in curves}
    (OUT / "scenarios.json").write_text(json.dumps({"rounds": cfg["rounds"], "seed": seeds[0], "scenarios": sc, "all": curves}))
    return rows


def zk_stage(path="configs/phase3.yaml", on_round=None, write=True):
    """Real Phase 3 receipts through zk_check at four nodes. Verify only."""
    from experiments.run_phase3 import merged
    from zk.bridge import cli
    p3, cfg = merged(path)
    fr, zc = p3["fl_run"], p3["zk"]
    seed, K, batch = fr["seed"], cfg["fl"]["K"], cfg["fl"]["batch"]
    clients, test = data.load(seed, cfg["clients"])
    trees = [MerkleTree(d.X, d.y) for d in clients]
    lr_fx = int(fx.to_fx(cfg["fl"]["lr"]))
    B2 = fx.bound_sq(cfg["norm_bound_B"])
    zkp = zkpolicy.ZkPolicy(cli.verify_receipt, [len(d) for d in clients], K, batch, seed, lr_fx, B2, roots=[t.root for t in trees])
    pq_alg, cl_alg = cfg.get("sig_alg", "ML-DSA-65"), cfg.get("classical_alg", "Ed25519")
    sess = pqsession.Session("hybrid", pq_alg, cl_alg, cfg["clients"], N_AGG, seed, cfg.get("epoch_rounds", 5),
                             [t.root for t in trees], zk=zkp)
    net = Network(N_AGG)
    nodes = []
    for i in range(N_AGG):
        v = policy.Verifier(sess.registry, "hybrid", pq_alg, cl_alg, zk=zkp)
        nodes.append(Node(i, N_AGG, F, sess.registry, v, net, defence="fedavg", B2=B2, verify_update=zk_check(v), seed=seed))
    zdir = ROOT / zc["out_dir"]
    rows, w = [], model.init(seed)
    atk = fr["attacker"]

    async def body():
        nonlocal w
        for t in range(fr["rounds"]):
            sess.begin_round(t, w)
            ups = []
            for c in fr["honest"]:
                idx = client.sample_indices(seed, t, c, K, batch, len(clients[c]))
                d = client.local_train(w, clients[c], idx, lr_fx)
                rb = (zdir / f"r{t}_c{c}.receipt").read_bytes()
                ups.append(Update(c, sess.client_envelope(t, c, d, rb), d, rb))
            idx = client.sample_indices(seed, t, atk, K, batch, len(clients[atk]))
            d_bad = poison.scaled(client.local_train(w, clients[atk], idx, lr_fx), fr["attack_scale"])
            ups.append(Update(atk, sess.client_envelope(t, atk, d_bad), d_bad, None))
            t0 = time.perf_counter()
            await run_round(nodes, net, sess.registry, sess.algs, t, w, ups)
            lat = (time.perf_counter() - t0) * 1000
            fin = [n.finalized.get(t) for n in nodes]
            assert all(f is not None for f in fin), "round did not finalize at every node"
            assert len({f[0] for f in fin}) == 1, "nodes finalized different models"
            w = fin[0][1]
            rows.append(dict(round=t, accepted=str(nodes[0].accepted_ids(t)), finalized_at_nodes=len(fin),
                             model_hash=fin[0][0].hex()[:16], accuracy=round(model.accuracy(w, test), 4),
                             real_receipts_verified=len(fr["honest"]) * N_AGG, round_latency_ms=round(lat, 1),
                             attacker_reason=";".join(sorted({r for n in nodes for (rr, c, r) in n.drop_log() if rr == t and c == atk}))))
            print(rows[-1], flush=True)
            if on_round:
                on_round(dict(rows[-1]))

    asyncio.run(run_rounds_with(nodes, net, body))
    if write:
        _write(OUT / "zk_consensus.csv", rows)
    return rows


def _write(path, rows):
    if not rows:
        path.write_text("")
        return
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


def summary(rows):
    by = {}
    for r in rows:
        by.setdefault((r["attack"], r["defence"]), []).append(r["final_acc"])
    lines = ["| attack | defence | mean final acc | std | seeds |", "|---|---|---|---|---|"]
    for (a, d), v in by.items():
        lines.append(f"| {a} | {d} | {np.mean(v):.4f} | {np.std(v):.4f} | {len(v)} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/demo.yaml")
    ap.add_argument("--stage", choices=["scenarios", "zk"], default="scenarios")
    ap.add_argument("--attack", choices=ATTACKS + ["all"], default="scaled")
    ap.add_argument("--defence", choices=["on", "off", "both"], default="on")
    ap.add_argument("--rounds", type=int)
    ap.add_argument("--seeds", default=None, help="comma list, default from config")
    ap.add_argument("--all", action="store_true", help="everything: attack matrix on all seeds, then the real-receipt consensus stage")
    a = ap.parse_args()
    logging.disable(logging.WARNING)
    dc = load_cfg(a.config)
    cfg = load_cfg(dc["base"])
    if a.rounds:
        cfg["rounds"] = a.rounds
    seeds = [int(s) for s in a.seeds.split(",")] if a.seeds else dc["seeds"]
    if a.all:
        rows = scenarios(cfg, seeds, ATTACKS, ["off", "on"])
        (OUT / "scenarios_summary.md").write_text(summary(rows) + "\n")
        print(summary(rows))
        zk_stage(dc["zk_config"])
        return
    if a.stage == "zk":
        zk_stage(dc["zk_config"])
        return
    rows = scenarios(cfg, seeds, ATTACKS if a.attack == "all" else [a.attack],
                     ["off", "on"] if a.defence == "both" else [a.defence])
    print(summary(rows))


if __name__ == "__main__":
    main()
