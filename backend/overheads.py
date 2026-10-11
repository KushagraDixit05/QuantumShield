"""GET /api/overheads: stored bench files, plus per attack/defence means computed from scenarios.csv."""
from . import hardware
from .common import RES, read_csv, read_text, rel


def _sec(name):
    p = RES / name
    _, rows = read_csv(p)
    return dict(source=rel(p), rows=rows)


def load():
    sc = RES / "scenarios.csv"
    _, rows = read_csv(sc)
    groups = {}
    for r in rows:
        groups.setdefault((r["attack"], r["defence"]), []).append(r)

    def mean(rs, k):
        v = [r[k] for r in rs if r[k] is not None]
        return sum(v) / len(v) if v else None

    per = [dict(attack=a, defence=d, seeds=len(rs), mean_round_latency_ms=mean(rs, "mean_round_latency_ms"),
                mean_update_env_bytes=mean(rs, "mean_update_env_bytes"),
                n_diverged=sum(1 for r in rs if r["diverged_round"] is not None))
           for (a, d), rs in groups.items()]
    md = RES / "overheads.md"
    return dict(hardware=hardware.parse(),
                signatures=_sec("sig_bench.csv"), envelope=_sec("sig_bench_overhead.csv"),
                throughput=_sec("sig_bench_throughput.csv"), zk=_sec("zk_bench.csv"),
                round=dict(source=rel(sc), rows=per,
                           note="means over seeds of the per-run means in scenarios.csv; latency excludes rounds not run after a divergence",
                           mean_round_latency_ms=mean(rows, "mean_round_latency_ms"),
                           mean_update_env_bytes=mean(rows, "mean_update_env_bytes")),
                markdown=dict(source=rel(md), text=read_text(md)))
