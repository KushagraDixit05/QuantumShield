"""Figures for the Phase 5 scenarios, built only from the result files (never hand-edited).

  python -m demo.plot                      # writes accuracy.png and attack_matrix.png into demo/results/
  python -m demo.plot [results.json] [out.png]   # accuracy figure only

accuracy.png     : seed-0 test accuracy vs round for A (benign), B (poisoned, plain FedAvg), C (poisoned,
                   QuantumShield on), from scenarios.json {"scenarios": {"A": [acc_0..acc_R], ...}}.
                   Index 0 is the initial model. B's trailing 0.0 values are the divergence convention (D-012).
attack_matrix.png: mean final accuracy +- std over seeds for attack x defence, from scenarios.csv.
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS = Path(__file__).resolve().parent / "results"
LABELS = {"A": "A: benign, no attack", "B": "B: poisoned, plain FedAvg", "C": "C: poisoned, QuantumShield on"}
STYLE = {"A": dict(color="#4c78a8", ls="-", marker="o"), "B": dict(color="#d55e00", ls="--", marker="s"),
         "C": dict(color="#2a9d5c", ls="-", marker="^")}
ATTACKS = ["none", "scaled", "forged", "replay"]
DEFENCES = ["off", "on"]
DEF_COLOR = {"off": "#d55e00", "on": "#2a9d5c"}
INK, MUTED = "#222222", "#666666"
N_TEST = 359


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)


def plot(results, out):
    sc = results.get("scenarios") if isinstance(results, dict) else None
    if not sc:
        raise ValueError("no scenarios in results")
    for k, ys in sc.items():
        if not isinstance(ys, list) or not ys:
            raise ValueError(f"scenario {k!r} has no accuracy curve")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    _style(ax)
    for k in sorted(sc):
        ys = sc[k]
        ax.plot(range(len(ys)), ys, label=LABELS.get(k, k), lw=2, ms=5, **STYLE.get(k, {}))
    if "B" in sc:
        ys = sc["B"]
        z = next((i for i, v in enumerate(ys) if i > 0 and v == 0.0), None)
        if z is not None:
            ax.annotate("B diverged (int64 overflow);\n0.0 is a convention (D-012),\nnot a measured accuracy",
                        xy=(z, 0.0), xytext=(max(z - 4.3, 0.2), 0.27), fontsize=8.5, color=INK,
                        arrowprops=dict(arrowstyle="->", color=MUTED))
    ax.set_xlabel("round (0 = initial model)", color=INK)
    ax.set_ylabel("test accuracy", color=INK)
    ax.set_ylim(0, 1.0)
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.5), frameon=False)
    ax.set_title("Accuracy vs round, seed 0", loc="left", fontsize=12, color=INK)
    fig.tight_layout()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def load_matrix(csv_path):
    """-> {(attack, defence): [final_acc per seed]}."""
    cells = {}
    with open(csv_path, newline="") as f:
        rd = csv.DictReader(f)
        need = {"attack", "defence", "final_acc"}
        if not rd.fieldnames or not need <= set(rd.fieldnames):
            raise ValueError(f"{csv_path}: need columns {sorted(need)}")
        for row in rd:
            cells.setdefault((row["attack"], row["defence"]), []).append(float(row["final_acc"]))
    if not cells:
        raise ValueError(f"{csv_path}: no rows")
    return cells


def plot_matrix(csv_path, out):
    cells = load_matrix(csv_path)
    attacks = [a for a in ATTACKS if any((a, d) in cells for d in DEFENCES)]
    if not attacks:
        raise ValueError("no known attacks in csv")
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    _style(ax)
    w, x = 0.36, np.arange(len(attacks))
    for j, d in enumerate(DEFENCES):
        m = [np.mean(cells[(a, d)]) if (a, d) in cells else np.nan for a in attacks]
        s = [np.std(cells[(a, d)]) if (a, d) in cells else 0 for a in attacks]
        pos = x + (j - 0.5) * w
        ax.bar(pos, m, w * 0.92, yerr=s, capsize=3, color=DEF_COLOR[d], label=f"defence {d}",
               error_kw=dict(ecolor=INK, lw=1))
        for p, v in zip(pos, m):
            if v < 0.01:
                ax.text(p, 0.02, "0.0\n(diverged)", ha="center", va="bottom", fontsize=8.5, color=INK)
            elif not np.isnan(v):
                ax.text(p, 0.015, f"{v:.3f}", ha="center", va="bottom", fontsize=8.5, color="white",
                        rotation=90 if v > 0.05 else 0)
    ax.set_xticks(x)
    ax.set_xticklabels(attacks)
    ax.set_xlabel("attack", color=INK)
    ax.set_ylabel("final test accuracy (mean, bar = std over seeds)", color=INK)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2, frameon=False)
    ax.set_title("Attack x defence, final accuracy", loc="left", fontsize=12, color=INK, pad=28)
    fig.text(0.01, 0.01, f"Test set has {N_TEST} samples: differences of 1-2 points are suggestive only.\n"
             "Diverged runs (plain FedAvg under scaled/forged) are scored 0.0 by convention D-012.",
             fontsize=8, color=MUTED, va="bottom")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    if len(sys.argv) > 1:
        src = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else str(RESULTS / "accuracy.png")
        plot(json.loads(Path(src).read_text()), out)
        print(f"wrote {out}")
        return
    plot(json.loads((RESULTS / "scenarios.json").read_text()), RESULTS / "accuracy.png")
    print(f"wrote {RESULTS / 'accuracy.png'}")
    plot_matrix(RESULTS / "scenarios.csv", RESULTS / "attack_matrix.png")
    print(f"wrote {RESULTS / 'attack_matrix.png'}")


if __name__ == "__main__":
    main()
