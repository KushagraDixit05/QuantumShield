"""Phase 3 proving benchmark.   python -m experiments.zk.bench --config configs/phase3.yaml

Real proofs only (qs-zk prove, composite unless --kinds says otherwise), serialised by the prove lock inside
qs-zk. Run i proves the i-th honest vector of experiments/zk/bench.yaml (distinct inputs, no cache). Per run:
prove_s, verify_s (wall of `qs-zk verify`), receipt_bytes, cycles, user_cycles, segments, peak_rss_kb (from the
prove stats) and agg_check_s (pq Session.admit with the receipt: signature + commitment + proof_hash + the
real verify). Writes demo/results/zk_bench.csv and .md with a hardware line and median/min/max.

--dry: builds the same inputs and calls `qs-zk execute` only. That is EXECUTION, not proving: no receipt is
made and no timing from it is a proving cost. Nothing is written in dry mode.
--kinds composite,succinct: compare kinds at vector 0 (does not run unless asked; succinct uses more memory).
"""
import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fl import zk_reference as zr  # noqa: E402
from pq import envelope as ev  # noqa: E402
from pq import session as pqsession  # noqa: E402
from pq import zkpolicy  # noqa: E402
from zk.bridge import cli  # noqa: E402

FIELDS = ["run", "vector", "kind", "po2", "prove_s", "verify_s", "agg_check_s", "receipt_bytes", "cycles",
          "user_cycles", "segments", "peak_rss_kb"]


def load(path):
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    cfg = yaml.safe_load(p.read_text())
    if "base" in cfg:
        base = load(cfg.pop("base"))
        base.update(cfg)
        cfg = base
    return cfg


def hardware():
    cpu = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), "unknown CPU")
    n = sum(1 for l in open("/proc/cpuinfo") if l.startswith("processor"))
    mem = next((int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemTotal")), 0)
    return f"{cpu}, {n} logical CPUs, {mem / 1048576:.1f} GiB RAM"


def agg_check(blob, receipt):
    """Aggregator-side time: Session.admit of a hybrid-signed v2 envelope built from the blob's public fields."""
    p = zr.parse_input(blob)
    n_cl = max(5, p["c"] + 1)
    roots, n_c = [bytes(32)] * n_cl, [1] * n_cl
    roots[p["c"]], n_c[p["c"]] = p["R"], p["n_c"]
    zk = zkpolicy.ZkPolicy(cli.verify_receipt, n_c, p["K"], p["batch"], p["seed"], p["lr_fx"], p["B2"])
    sess = pqsession.Session("hybrid", "ML-DSA-65", "Ed25519", n_cl, 4, p["seed"], 5, roots, zk=zk)
    sess.begin_round(p["t"], p["w_t"])
    assert ev.model_hash(p["w_t"]) == p["h_w"]
    env = ev.sign_update(sess.registry, sess.algs, p["t"], p["c"], p["h_w"], p["delta"], p["R"], p["nonce"],
                         ev.proof_hash(receipt))
    t0 = time.time()
    ok = sess.admit(p["t"], p["c"], env, p["delta"], receipt)
    return time.time() - t0, ok, (sess.drop_log[-1][2] if sess.drop_log else "ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/phase3.yaml")
    ap.add_argument("--bench-config", default="experiments/zk/bench.yaml")
    ap.add_argument("--dry", action="store_true", help="qs-zk execute only (NOT proving); writes nothing")
    ap.add_argument("--kinds", default=None, help="comma list, e.g. composite,succinct: compare at vector 0")
    ap.add_argument("--repeats", type=int, default=None)
    a = ap.parse_args()
    cfg = load(a.config)
    bc = load(a.bench_config)["bench"]
    po2 = cfg["zk"]["po2"]
    n = a.repeats or bc["repeats"]
    vdir = ROOT / bc["vector_dir"]
    names = bc["vectors"]
    if a.kinds:
        plan = [(i, names[0], k) for i, k in enumerate(a.kinds.split(","))]
    else:
        k0 = cfg["zk"].get("receipt_kind", "composite")
        plan = [(i, names[i], k0) for i in range(min(n, len(names)))]
    hw = hardware()
    iid = cli.image_id()
    print(f"hardware: {hw}\nimage_id: {iid}\nconfig K={cfg['fl']['K']} batch={cfg['fl']['batch']} po2={po2}")

    if a.dry:
        print("*** DRY RUN: qs-zk EXECUTE only. This is execution in the zkVM executor, NOT proving; "
              "no receipt is produced and none of these timings is a proving cost. ***")
        for i, name, kind in plan:
            blob = (vdir / f"{name}.in.bin").read_bytes()
            t0 = time.time()
            ok, journal, st = cli.execute(blob)
            print(f"[execute-only] run={i} vector={name} relation_holds={ok} wall={time.time() - t0:.2f}s "
                  f"cycles={st.get('cycles')} user_cycles={st.get('user_cycles')} segments={st.get('segments')} "
                  f"journal_matches_blob_head={journal == blob[:146] if ok else None}")
        return

    work = ROOT / bc["work_dir"]
    work.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, name, kind in plan:
        blob = (vdir / f"{name}.in.bin").read_bytes()
        rp, jp = work / f"{name}.{kind}.receipt", work / f"{name}.{kind}.journal"
        st = cli.prove_update(blob, rp, jp, po2=po2, kind=kind)
        assert not st.get("dev_mode"), "dev mode receipt: refusing to record"
        rb = rp.read_bytes()
        t0 = time.time()
        ok, why = cli.verify_receipt(rb, blob[:146])
        vs = time.time() - t0
        assert ok, f"verify failed: {why}"
        ag, aok, areason = agg_check(blob, rb)
        assert aok, f"aggregator rejected honest receipt: {areason}"
        rows.append(dict(run=i, vector=name, kind=kind, po2=po2, prove_s=st["prove_s"], verify_s=round(vs, 3),
                         agg_check_s=round(ag, 3), receipt_bytes=st["receipt_bytes"], cycles=st["cycles"],
                         user_cycles=st["user_cycles"], segments=st["segments"], peak_rss_kb=st["peak_rss_kb"]))
        print(rows[-1], flush=True)
    out_csv, out_md = ROOT / bc["out_csv"], ROOT / bc["out_md"]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    lines = ["# ZK proving benchmark (real RISC Zero proofs, no dev mode)", "",
             f"- Hardware: {hw}", f"- Guest image id: `{iid}`",
             f"- Config: K={cfg['fl']['K']}, batch={cfg['fl']['batch']}, po2={po2}, relation={cfg['zk']['relation']}",
             f"- Runs: {len(rows)} ({', '.join(sorted({r['kind'] for r in rows}))}); run i proves a distinct honest vector", "",
             "| run | vector | kind | prove_s | verify_s | agg_check_s | receipt_bytes | cycles | user_cycles | segments | peak_rss_MB |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['run']} | {r['vector']} | {r['kind']} | {r['prove_s']} | {r['verify_s']} | {r['agg_check_s']} | "
                     f"{r['receipt_bytes']} | {r['cycles']} | {r['user_cycles']} | {r['segments']} | {r['peak_rss_kb'] // 1024} |")
    lines += ["", "| metric | median | min | max |", "|---|---|---|---|"]
    for k in ["prove_s", "verify_s", "agg_check_s", "receipt_bytes", "cycles", "user_cycles", "segments", "peak_rss_kb"]:
        v = [r[k] for r in rows]
        lines.append(f"| {k} | {statistics.median(v)} | {min(v)} | {max(v)} |")
    lines += ["", "verify_s = wall clock of one `qs-zk verify` call (includes process start). agg_check_s = "
              "`Session.admit` with a hybrid-signed v2 envelope (signatures + commitment + proof_hash + real verify)."]
    out_md.write_text("\n".join(lines) + "\n")
    print(f"wrote {out_csv} and {out_md}")


if __name__ == "__main__":
    main()
