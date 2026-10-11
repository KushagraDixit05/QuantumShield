"""Whitelisted stored results + the computed attack matrix. Names map to fixed files; no path is ever built from input."""
import json
import statistics

from fastapi import HTTPException

from .common import RES, d012_note, read_csv, read_text, rel

CSV = {"scenarios": "scenarios.csv", "rejections": "rejections.csv", "baseline": "baseline.csv",
       "phase2_fl": "phase2_fl.csv", "phase3_fl": "phase3_fl.csv", "sig_bench": "sig_bench.csv",
       "sig_bench_overhead": "sig_bench_overhead.csv", "sig_bench_throughput": "sig_bench_throughput.csv",
       "zk_bench": "zk_bench.csv", "zk_consensus": "zk_consensus.csv"}
NAMES = list(CSV) + ["scenarios_curves", "overheads", "attack_matrix"]
DIVERGENCE_NAMES = ("scenarios", "scenarios_curves", "attack_matrix")


def attack_matrix(rows):
    """attack x defence from scenarios.csv rows. Diverged seeds (stored final_acc 0.0 by convention, D-012) are excluded from
    mean/std; the cell then carries `diverged: "k of n"` and accuracy_is_plain false."""
    cells = {}
    for r in rows:
        cells.setdefault((r["attack"], r["defence"]), []).append(r)
    out = []
    for (a, d), rs in cells.items():
        ok = [r["final_acc"] for r in rs if r["diverged_round"] is None]
        nd = len(rs) - len(ok)
        out.append(dict(attack=a, defence=d, n_seeds=len(rs), n_diverged=nd,
                        diverged=f"{nd} of {len(rs)}" if nd else None,
                        n_accuracy_seeds=len(ok),
                        mean_final_acc=statistics.fmean(ok) if ok else None,
                        std_final_acc=statistics.pstdev(ok) if ok else None,
                        accuracy_is_plain=nd == 0,
                        rejected_total=sum(r["rejected"] for r in rs),
                        seeds=[r["seed"] for r in rs]))
    return out


def get(name):
    if name not in NAMES:
        raise HTTPException(404, f"unknown result {name!r}")
    resp = dict(name=name)
    if name in CSV:
        p = RES / CSV[name]
        cols, rows = read_csv(p)
        resp.update(source=[rel(p)], columns=cols, rows=rows)
    elif name == "scenarios_curves":
        p = RES / "scenarios.json"
        resp.update(source=[rel(p)], columns=[], rows=[], json=json.loads(read_text(p)))
    elif name == "overheads":
        p = RES / "overheads.md"
        resp.update(source=[rel(p)], columns=[], rows=[], markdown=read_text(p))
    else:
        p = RES / "scenarios.csv"
        _, rows = read_csv(p)
        cols = ["attack", "defence", "n_seeds", "n_diverged", "diverged", "n_accuracy_seeds", "mean_final_acc",
                "std_final_acc", "accuracy_is_plain", "rejected_total", "seeds"]
        resp.update(source=[f"computed by backend.results.attack_matrix from {rel(p)} (not a stored file)"],
                    columns=cols, rows=attack_matrix(rows))
    if name in DIVERGENCE_NAMES:
        resp["diverged_note"] = d012_note()
    return resp
