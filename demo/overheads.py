"""Overhead table (demo/results/overheads.md): what QuantumShield adds per update.

Signature bytes and sign/verify times are measured now (pq/bench.py primitives + real envelope encoding).
Every ZK number is read from the existing real-proof files (the prover is never run here):
  zk_bench.csv (K=4, batch 8 proofs), phase3_fl.csv (FL integration proofs), zk_consensus.csv (4-node consensus).
Consensus latency without/with the defence comes from scenarios.csv.
Usage: python -m demo.overheads [--results DIR] [--zk-json PATH] [--out PATH]
--zk-json is an optional override: {"proof_bytes": int, "prove_s": float, "verify_ms": float}.
"""
import argparse
import csv
import json
import statistics as st
from pathlib import Path

import numpy as np

ALGS = ["Ed25519", "ML-DSA-65"]
DELTA_BYTES = 2410 * 8          # int64 delta vector, same as pq.bench.UPDATE_BYTES
VARIABILITY = "1.6x"


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _nums(rows, key):
    out = []
    for r in rows:
        try:
            if r.get(key, "") != "":
                out.append(float(r[key]))
        except ValueError:
            pass
    return out


def parse_zk_bench(path):
    rows = read_csv(path)
    p, v, rc = _nums(rows, "prove_s"), _nums(rows, "verify_s"), _nums(rows, "receipt_bytes")
    return {"runs": len(p), "prove_med": st.median(p), "prove_min": min(p), "prove_max": max(p),
            "verify_ms": st.median(v) * 1000, "receipt_bytes": int(st.median(rc)), "src": Path(path).name}


def parse_phase3(path):
    rows = [r for r in read_csv(path) if r.get("prove_s") not in (None, "") and r.get("role") == "honest"]
    p = _nums(rows, "prove_s")
    return {"n": len(p), "prove_min": min(p), "prove_max": max(p), "src": Path(path).name}


def parse_scenarios(path):
    rows = read_csv(path)
    out = {}
    for d in ("off", "on"):
        sel = [r for r in rows if r["defence"] == d]
        out[d] = {"latency_ms": st.mean(_nums(sel, "mean_round_latency_ms")),
                  "env_bytes": int(round(st.mean(_nums(sel, "mean_update_env_bytes")))), "n": len(sel)}
    out["src"] = Path(path).name
    return out


def parse_consensus(path):
    rows = read_csv(path)
    return {"latency_ms": st.mean(_nums(rows, "round_latency_ms")), "rounds": len(rows),
            "receipts": int(st.mean(_nums(rows, "real_receipts_verified"))),
            "nodes": int(st.mean(_nums(rows, "finalized_at_nodes"))), "src": Path(path).name}


def load_zk(results, override=None):
    results = Path(results)
    z = {"bench": parse_zk_bench(results / "zk_bench.csv"), "fl": parse_phase3(results / "phase3_fl.csv"),
         "scen": parse_scenarios(results / "scenarios.csv"), "cons": parse_consensus(results / "zk_consensus.csv")}
    if override:
        b = z["bench"]
        b["receipt_bytes"] = int(override.get("proof_bytes", b["receipt_bytes"]))
        b["prove_med"] = b["prove_min"] = b["prove_max"] = float(override.get("prove_s", b["prove_med"]))
        b["verify_ms"] = float(override.get("verify_ms", b["verify_ms"]))
        b["src"] += " (overridden by --zk-json)"
    return z


def measure(reps=20):
    from pq import bench
    from pq import registry as rg
    reg = rg.KeyRegistry(1, 1, ALGS, seed=0)
    rng = np.random.default_rng(0)
    r = {"reps": reps, "hardware": bench.hardware()}
    for mode, algs in (("classical", ["Ed25519"]), ("pq", ["ML-DSA-65"]), ("hybrid", ALGS)):
        r[mode] = dict(zip(("upd_overhead", "upd_wire", "vote_overhead"), bench.envelope_overhead(reg, algs)))
    for alg in ALGS:
        r[alg] = bench.primitives(alg, {"keygen": 5, "sign": reps, "sign_slow": 3, "verify": reps}, rng)
    return r


def table(r, z):
    b, fl, sc, co = z["bench"], z["fl"], z["scen"], z["cons"]
    base = r["classical"]["upd_wire"] - r["classical"]["upd_overhead"]
    rc = b["receipt_bytes"]
    env_off, env_on = sc["off"]["env_bytes"], sc["on"]["env_bytes"]
    sig = lambda a: f"{r[a]['sign_ms_med']:.3f}"
    ver = lambda a: f"{r[a]['verify_ms_med']:.3f}"
    hy_s = r["Ed25519"]["sign_ms_med"] + r["ML-DSA-65"]["sign_ms_med"]
    hy_v = r["Ed25519"]["verify_ms_med"] + r["ML-DSA-65"]["verify_ms_med"]
    rows = [
        ("signature bytes / update, Ed25519 only", f"{r['classical']['upd_overhead']}", "n/a (this is the classical baseline)", "measured now"),
        ("signature bytes / update, ML-DSA-65", f"{r['pq']['upd_overhead']}", f"{r['classical']['upd_overhead']} (Ed25519)", "measured now"),
        ("signature bytes / update, hybrid Ed25519 + ML-DSA-65", f"{r['hybrid']['upd_overhead']}", f"{r['classical']['upd_overhead']} (Ed25519)", "measured now"),
        ("sign time (ms, median): Ed25519 / ML-DSA-65 / hybrid (sum)", f"{sig('Ed25519')} / {sig('ML-DSA-65')} / {hy_s:.3f}", f"{sig('Ed25519')} (Ed25519)", "measured now"),
        ("verify time (ms, median): Ed25519 / ML-DSA-65 / hybrid (sum)", f"{ver('Ed25519')} / {ver('ML-DSA-65')} / {hy_v:.3f}", f"{ver('Ed25519')} (Ed25519)", "measured now"),
        ("proof size (bytes, composite receipt, K=4 batch 8)", f"{rc:,}", "0 (no proof)", f"{b['src']}, median of {b['runs']} real proofs"),
        ("prove time (s / update)", f"{b['prove_med']:.1f} (range {b['prove_min']:.1f}-{b['prove_max']:.1f}; FL integration runs {fl['prove_min']:.0f}-{fl['prove_max']:.0f}, about {VARIABILITY} run-to-run variability)", "0",
         f"{b['src']} ({b['runs']} runs); {fl['src']} ({fl['n']} proofs)"),
        ("verify time (ms / proof, qs-zk CLI incl. process start)", f"{b['verify_ms']:.0f}", "0", b["src"]),
        ("per-round consensus latency (ms), signatures + defence", f"{sc['on']['latency_ms']:.1f}", f"{sc['off']['latency_ms']:.1f}",
         f"{sc['src']}, mean_round_latency_ms over {sc['off']['n']} defence-off / {sc['on']['n']} defence-on runs"),
        (f"per-round consensus latency (ms), with real receipt verification ({co['nodes']} nodes, {co['receipts']} receipts/round)", f"{co['latency_ms']:.1f}", f"{sc['off']['latency_ms']:.1f}",
         f"{co['src']}, mean of {co['rounds']} rounds; excludes proving"),
        ("bandwidth / update (bytes): envelope", f"{env_on}", f"{env_off}", f"{sc['src']} mean_update_env_bytes (defence on / off)"),
        ("bandwidth / update (bytes): envelope + delta vector", f"{env_on + DELTA_BYTES:,}", f"{env_off + DELTA_BYTES:,}", f"delta = 2410 x 8 = {DELTA_BYTES:,} B"),
        ("bandwidth / update (bytes): envelope + delta + receipt", f"{env_on + DELTA_BYTES + rc:,}", f"{env_off + DELTA_BYTES:,}", f"receipt bytes from {b['src']}"),
    ]
    out = ["# Overheads", "",
           f"Hardware: {r['hardware']}",
           "",
           f"Signature bytes and sign/verify times were measured now with {r['reps']} repetitions. Payload-only baseline = {base} B (update envelope, no signature). "
           f"Every ZK row is read from the existing real-proof files named in the last column; the prover was not run here and RISC0_DEV_MODE is not used.",
           "",
           "Notes:",
           "- The network is simulated in-process, so the latency rows are compute time, not network time.",
           "- Prove time per update is about 6-10 minutes (about 6.5 min on a quiet machine, up to about 10 min under load), so proving every update in a round is not interactive.",
           f"- Prove time varies by about {VARIABILITY} run-to-run on this machine; treat it as a range.",
           "- Without QuantumShield = the Ed25519-signed baseline (defence off in scenarios.csv); the proof columns have no baseline cost.",
           "",
           "| metric | with QuantumShield | without | source |", "|---|---|---|---|"]
    out += [f"| {a} | {x} | {y} | {s} |" for a, x, y, s in rows]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="demo/results")
    ap.add_argument("--zk-json", help="optional override of proof_bytes/prove_s/verify_ms")
    ap.add_argument("--out", default="demo/results/overheads.md")
    a = ap.parse_args()
    ov = json.loads(Path(a.zk_json).read_text()) if a.zk_json else None
    md = table(measure(), load_zk(a.results, ov))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(md)
    print(md)


if __name__ == "__main__":
    main()
