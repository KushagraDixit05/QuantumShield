"""One command: python -m experiments.run_baseline --config configs/baseline.yaml
Calibrates B from benign update norms (if norm_bound_B is null or --calibrate), then runs the grid."""
import argparse
import csv
import re
import time

import numpy as np

from fl import fixedpoint as fx
from fl.simulate import ROOT, load_cfg, run


def calibrate(cfg, bcfg):
    _, norms = run(cfg, "none", "fedavg", bcfg["calibration_seed"], return_norms=True)
    n = np.sqrt(np.array(norms, dtype=np.float64)) / fx.ONE
    p = float(np.percentile(n, bcfg["calibration_percentile"]))
    return round(p * bcfg["calibration_margin"], 4), p, float(n.max()), float(np.median(n))


def write_B(B):
    f = ROOT / "configs/mvp.yaml"
    t = f.read_text()
    f.write_text(re.sub(r"^norm_bound_B:.*$", f"norm_bound_B: {B}", t, flags=re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/baseline.yaml")
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    bcfg = load_cfg(a.config)
    cfg = load_cfg(bcfg["base"])
    if a.calibrate or not cfg.get("norm_bound_B"):
        B, p, mx, med = calibrate(cfg, bcfg)
        write_B(B)
        cfg["norm_bound_B"] = B
        print(f"calibration seed={bcfg['calibration_seed']}: benign ||Δ|| median={med:.4f} "
              f"p{bcfg['calibration_percentile']}={p:.4f} max={mx:.4f} -> B={B}")
    B = cfg["norm_bound_B"]
    B2 = fx.bound_sq(B)
    rows = []
    t0 = time.time()
    for atk in bcfg["attacks"]:
        for dfn in bcfg["defences"]:
            for seed in bcfg["seeds"]:
                st = {}
                acc = run(cfg, atk, dfn, seed, B2, stats=st)
                rows.append(dict(attack=atk, defence=dfn, seed=seed, final_acc=acc[-1],
                                 benign_rejected=st.get("benign_rejected", 0), mal_rejected=st.get("mal_rejected", 0), diverged=int("diverged_round" in st),
                                 benign_total=st.get("benign_total", 0), mal_total=st.get("mal_total", 0),
                                 curve=" ".join(f"{x:.4f}" for x in acc)))
                print(f"{atk:11s} {dfn:11s} seed={seed} final={acc[-1]:.4f}", flush=True)
    out = ROOT / bcfg["out_csv"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader(); wr.writerows(rows)
    # markdown table: mean ± std over seeds
    md = [f"B = {B} (||Δ||), seeds = {bcfg['seeds']}, final-round test accuracy, mean ± std (population std); diverged runs (int64 range exceeded) score 0.0",
          "", "| attack | " + " | ".join(bcfg["defences"]) + " | norm-check rejections (malicious / benign, of all client-rounds) |",
          "|---|" + "---|" * (len(bcfg["defences"]) + 1)]
    for atk in bcfg["attacks"]:
        cells = []
        for dfn in bcfg["defences"]:
            v = np.array([r["final_acc"] for r in rows if r["attack"] == atk and r["defence"] == dfn])
            nd = sum(r["diverged"] for r in rows if r["attack"] == atk and r["defence"] == dfn)
            cells.append(f"{v.mean():.4f} ± {v.std():.4f}" + (f" (diverged {nd}/{len(v)})" if nd else ""))
        sel = [r for r in rows if r["attack"] == atk and r["defence"] == "norm_filter"]
        mr = sum(r["mal_rejected"] for r in sel); br = sum(r["benign_rejected"] for r in sel)
        tot_m = sum(r["mal_total"] for r in sel); tot_b = sum(r["benign_total"] for r in sel)
        md.append(f"| {atk} | " + " | ".join(cells) + f" | {mr}/{tot_m} / {br}/{tot_b} |")
    (ROOT / bcfg["out_md"]).write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"done in {time.time() - t0:.1f}s -> {bcfg['out_csv']}, {bcfg['out_md']}")


if __name__ == "__main__":
    main()
