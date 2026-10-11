"""Hardware description parsed from demo/results/zk_bench.md and docs/zk_cost.md (nothing retyped)."""
import re

from .common import RES, ROOT, read_text

BENCH = RES / "zk_bench.md"
COST = ROOT / "docs" / "zk_cost.md"
SRC = "demo/results/zk_bench.md, docs/zk_cost.md"


def parse():
    bench = read_text(BENCH)
    cost = read_text(COST)
    m = re.search(r"^- Hardware:\s*(.+)$", bench, re.M)
    cpu = ram = threads = None
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        cpu = parts[0]
        for p in parts[1:]:
            if "logical CPU" in p:
                threads = int(p.split()[0])
            elif "RAM" in p:
                ram = p.replace("RAM", "").strip()
    os_m = re.search(r"Linux [\w.\-]+", cost)
    zk_m = re.search(r"risc0-zkvm [\d.]+", cost)
    cpu_proving = "CPU proving" in cost
    return dict(cpu=cpu, threads=threads, ram=ram, os=os_m.group(0) if os_m else None,
                gpu_used=False, zkvm=zk_m.group(0) if zk_m else None, source=SRC,
                note="CPU proving" if cpu_proving else None)
