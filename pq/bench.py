"""Signature benchmark.  python -m pq.bench --config configs/phase2.yaml

Per algorithm: keygen / sign / verify time (mean, median, p95), public key and signature sizes,
bytes the signature layer adds to each envelope. Then verification throughput of the real
aggregator path (Verifier.verify_envelope: key checks + signature(s) + commitment + nonce) at
50 / 100 / 500 simulated clients. Algorithms run one at a time, sequentially, in one process.
Timing uses liboqs's system RNG (a Python RNG callback would add overhead to the measurement);
messages, deltas and keys for the throughput part are seeded.
"""
import argparse
import csv
import gc
import platform
import time

import numpy as np
import oqs
import cryptography

from fl.simulate import ROOT, load_cfg

from . import envelope as ev
from . import policy, sig
from . import registry as rg

UPDATE_BYTES = 2410 * 8


def hardware():
    cpu = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), platform.processor())
    mem = next((int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemTotal")), 0) / 1024 / 1024
    return (f"{cpu}, {len(__import__('os').sched_getaffinity(0))} threads, {mem:.1f} GiB RAM, {platform.system()} {platform.release()}, "
            f"Python {platform.python_version()}, liboqs {oqs.oqs_version()}, liboqs-python {oqs.oqs_python_version()}, "
            f"cryptography {cryptography.__version__}, single process, sequential")


def _times(fn, reps):
    out = []
    for _ in range(reps):
        t0 = time.perf_counter_ns()
        fn()
        out.append((time.perf_counter_ns() - t0) / 1e6)  # ms
    a = np.array(out)
    return float(a.mean()), float(np.median(a)), float(np.percentile(a, 95))


def primitives(alg, reps, rng):
    sig.seed_rng(None)
    msg = rng.bytes(ev.UPDATE_LEN + 12)                   # about the size of the signed bytes
    kg = _times(lambda: sig.keygen(alg), reps["keygen"])
    pk, sk = sig.keygen(alg)
    sg = _times(lambda: sig.sign(alg, sk, msg), reps["sign_slow" if alg == "SLH-DSA-128s" else "sign"])
    s = sig.sign(alg, sk, msg)
    assert sig.verify(alg, pk, msg, s)
    vf = _times(lambda: sig.verify(alg, pk, msg, s), reps["verify"])
    return dict(alg=alg, pk_bytes=len(pk), sig_bytes=len(s), sig_bytes_max=sig.sizes(alg)[1],
                keygen_ms_mean=kg[0], keygen_ms_med=kg[1], keygen_ms_p95=kg[2],
                sign_ms_mean=sg[0], sign_ms_med=sg[1], sign_ms_p95=sg[2],
                verify_ms_mean=vf[0], verify_ms_med=vf[1], verify_ms_p95=vf[2])


def envelope_overhead(registry, algs):
    """Bytes the signature layer adds to one update / one vote envelope (real wire encoding)."""
    d = np.zeros(2410, dtype=np.int64)
    e = ev.sign_update(registry, algs, 0, 0, bytes(32), d, bytes(32), bytes(32))
    v = ev.sign_payload(registry, "agg", 0, algs, ev.pack_vote(0, 0, bytes(32), bytes(32), bytes(32)))
    return e.overhead(), len(e.wire()), v.overhead()


def throughput(label, mode, pq_alg, algs, sizes, repeats, seed):
    n_max = max(sizes)
    reg = rg.KeyRegistry(n_max, 1, ["Ed25519", pq_alg], seed, 10 ** 9)
    rng = np.random.default_rng(seed)
    w = rng.integers(-1000, 1000, 2410, dtype=np.int64)
    h_w = ev.model_hash(w)
    deltas = [rng.integers(-5000, 5000, 2410, dtype=np.int64) for _ in range(n_max)]
    envs = [ev.sign_update(reg, algs, 0, c, h_w, deltas[c], bytes(32), ev.make_nonce(seed, 0, c)) for c in range(n_max)]
    over, total, vote_over = envelope_overhead(reg, algs)
    sig.seed_rng(None)
    rows = []
    for n in sizes:
        best = []
        for _ in range(repeats):
            v = policy.Verifier(reg, mode, pq_alg)
            v.begin_round(0, h_w)
            t0 = time.perf_counter()
            ok = sum(v.verify_envelope(envs[c], deltas[c])[0] for c in range(n))
            best.append(time.perf_counter() - t0)
            assert ok == n
        t = float(np.median(best))
        rows.append(dict(config=label, clients=n, total_ms=t * 1e3, ms_per_envelope=t * 1e3 / n, envelopes_per_s=n / t))
    return rows, dict(config=label, envelope_overhead_bytes=over, envelope_total_bytes=total, vote_overhead_bytes=vote_over,
                      round_overhead_bytes_5clients_4votes=5 * over + 4 * vote_over,
                      overhead_pct_of_update=100 * over / UPDATE_BYTES)


def fmt(x):
    return f"{x:.3f}" if x < 10 else f"{x:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/phase2.yaml")
    a = ap.parse_args()
    cfg = load_cfg(a.config)["bench"]
    rng = np.random.default_rng(cfg["seed"])
    prim = []
    for alg in cfg["algs"]:
        prim.append(primitives(alg, cfg["reps"], rng))
        gc.collect()
        p = prim[-1]
        print(f"{alg:13s} keygen {p['keygen_ms_med']:.3f} ms  sign {p['sign_ms_med']:.3f} ms  verify {p['verify_ms_med']:.3f} ms  "
              f"pk {p['pk_bytes']} B  sig {p['sig_bytes']} B", flush=True)
    tp, ov = [], []
    pq_default = cfg["hybrid_pq_alg"]
    configs = [(alg, "classical" if sig.kind(alg) == "classical" else "pq", alg, [alg]) for alg in cfg["algs"]]
    configs.append((f"hybrid(Ed25519+{pq_default})", "hybrid", pq_default, ["Ed25519", pq_default]))
    for label, mode, pq_alg, algs in configs:
        rows, o = throughput(label, mode, pq_alg if sig.kind(pq_alg) == "pq" else "ML-DSA-65", algs, cfg["clients"], cfg["repeats"], cfg["seed"])
        tp += rows
        ov.append(o)
        print(label, " ".join(f"{r['clients']}:{r['envelopes_per_s']:.0f}/s" for r in rows), flush=True)
        gc.collect()
    out = ROOT / cfg["out_prefix"]
    out.parent.mkdir(parents=True, exist_ok=True)
    for suffix, rows in (("", prim), ("_throughput", tp), ("_overhead", ov)):
        with open(f"{out}{suffix}.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
    hw = hardware()
    md = [f"Hardware/software: {hw}", "",
          f"Reps: {cfg['reps']}; message {ev.UPDATE_LEN + 12} B; system RNG; times are medians (ms), p95 in brackets.", "",
          "| algorithm | pk (B) | sig (B) | keygen ms | sign ms | verify ms |", "|---|---|---|---|---|---|"]
    for p in prim:
        md.append(f"| {p['alg']} | {p['pk_bytes']} | {p['sig_bytes']} | {fmt(p['keygen_ms_med'])} ({fmt(p['keygen_ms_p95'])}) | "
                  f"{fmt(p['sign_ms_med'])} ({fmt(p['sign_ms_p95'])}) | {fmt(p['verify_ms_med'])} ({fmt(p['verify_ms_p95'])}) |")
    md += ["", f"Falcon-512 signatures are variable length (reported = the sample observed; max {sig.sizes('Falcon-512')[1]} B).", "",
           "Bytes added by the signature layer (real wire encoding: signature(s), key ids, algorithm labels) per update envelope and per vote; "
           f"the update itself is {UPDATE_BYTES} B (2,410 int64):", "",
           "| config | per update envelope (B) | % of update | per vote (B) | per round, 5 clients + 4 votes (B) |", "|---|---|---|---|---|"]
    for o in ov:
        md.append(f"| {o['config']} | {o['envelope_overhead_bytes']} | {o['overhead_pct_of_update']:.1f}% | {o['vote_overhead_bytes']} | {o['round_overhead_bytes_5clients_4votes']} |")
    md += ["", "Aggregator verification throughput (full `verify_envelope` path, sequential, median of "
           f"{cfg['repeats']} runs), envelopes/s:", "",
           "| config | " + " | ".join(f"{n} clients" for n in cfg["clients"]) + " |", "|---|" + "---|" * len(cfg["clients"])]
    for label in dict.fromkeys(r["config"] for r in tp):
        md.append(f"| {label} | " + " | ".join(f"{r['envelopes_per_s']:.0f} ({r['total_ms']:.0f} ms total)" for r in tp if r["config"] == label) + " |")
    (ROOT / f"{cfg['out_prefix']}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
