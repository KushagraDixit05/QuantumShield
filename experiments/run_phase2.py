"""FL loop under every signature mode.  python -m experiments.run_phase2 --config configs/phase2.yaml

Table 1: scenario x mode, final-round accuracy (mean ± std over seeds) and drops by reason.
Table 2: the FL loop once per PQ algorithm (pq mode, benign, seed 0).
Also checks that the benign accuracy curves are identical across modes (signatures never alter a
delta, so any difference would be a bug)."""
import argparse
import csv
import logging
import time
from collections import Counter

import numpy as np

from fl import fixedpoint as fx
from fl.simulate import ROOT, load_cfg, run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/phase2.yaml")
    a = ap.parse_args()
    logging.disable(logging.WARNING)
    p2 = load_cfg(a.config)
    cfg = load_cfg(p2["base"])
    B2 = fx.bound_sq(cfg["norm_bound_B"])
    rows, curves = [], {}
    t0 = time.time()
    for sc in p2["fl_scenarios"]:
        for mode in p2["modes"]:
            if sc["env_attack"] and mode == "none":
                continue
            for seed in p2["seeds"]:
                st = {}
                acc = run(cfg, sc["attack"], sc["defence"], seed, B2, stats=st, signatures=mode, sig_alg=p2["pq_alg"], env_attack=sc["env_attack"])
                curves[(sc["name"], mode, seed)] = acc
                rows.append(dict(scenario=sc["name"], defence=sc["defence"], mode=mode, seed=seed, final_acc=acc[-1],
                                 diverged=int("diverged_round" in st), dropped=dict(st.get("dropped", {})),
                                 wire_bytes=st.get("wire_bytes", 0), votes_ok=st.get("votes_ok", 0), votes_bad=st.get("votes_bad", 0),
                                 curve=" ".join(f"{x:.4f}" for x in acc)))
                print(f"{sc['name']:45s} {mode:9s} seed={seed} final={acc[-1]:.4f} dropped={st.get('dropped', {})}", flush=True)
    md = [f"PQ scheme for pq/hybrid: {p2['pq_alg']}; seeds {p2['seeds']}; B = {cfg['norm_bound_B']}; final-round accuracy, mean ± std (population std); "
          "diverged = int64 range exceeded (scored 0.0, D-012).", "",
          "| scenario (defence) | " + " | ".join(p2["modes"]) + " |", "|---|" + "---|" * len(p2["modes"])]
    for sc in p2["fl_scenarios"]:
        cells = []
        for mode in p2["modes"]:
            rs = [r for r in rows if r["scenario"] == sc["name"] and r["mode"] == mode]
            if not rs:
                cells.append("n/a (needs signatures)")
                continue
            v = np.array([r["final_acc"] for r in rs])
            dr = Counter()
            for r in rs:
                dr.update(r["dropped"])
            nd = sum(r["diverged"] for r in rs)
            cells.append(f"{v.mean():.4f} ± {v.std():.4f}" + (f" (diverged {nd}/{len(v)})" if nd else "")
                         + (f"; dropped {dict(dr)}" if dr else ""))
        md.append(f"| {sc['name']} ({sc['defence']}) | " + " | ".join(cells) + " |")
    ident = all(curves[("benign", m, s)] == curves[("benign", "none", s)] for m in p2["modes"] for s in p2["seeds"])
    md += ["", f"Benign curves identical across all modes for every seed: {ident}"]
    # per-algorithm FL check
    md += ["", "FL loop per PQ algorithm (pq mode, benign, FedAvg, seed 0):", "", "| algorithm | final accuracy | identical to `none` | wall time (s) |", "|---|---|---|---|"]
    ref = curves[("benign", "none", p2["seeds"][0])]
    for alg in p2["all_algs"]:
        t1 = time.time()
        acc = run(cfg, "none", "fedavg", p2["seeds"][0], B2, signatures="pq", sig_alg=alg)
        md.append(f"| {alg} | {acc[-1]:.4f} | {acc == ref} | {time.time() - t1:.1f} |")
        print(f"alg {alg} final={acc[-1]:.4f} identical={acc == ref}", flush=True)
    out = ROOT / p2["out_fl"]
    with open(f"{out}.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    (ROOT / f"{p2['out_fl']}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"done in {time.time() - t0:.1f}s -> {p2['out_fl']}.csv/.md")


if __name__ == "__main__":
    main()
