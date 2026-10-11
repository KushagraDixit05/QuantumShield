"""Lead cross-check: run every vector through the real guest (qs-zk execute, no proving) and compare
accept/reject and journal bytes with the Python reference's expectation.
usage: python -m zk.crosscheck [vector_dir]"""
import json
import sys
from pathlib import Path

from fl import zk_reference as ref
from zk.bridge import cli

d = Path(sys.argv[1] if len(sys.argv) > 1 else "zk/bridge/vectors")
bad, n, acc = [], 0, 0
for f in sorted(d.glob("*.in.bin")):
    name = f.name[:-len(".in.bin")]
    exp = json.loads((d / f"{name}.expect.json").read_text())
    blob = f.read_bytes()
    r_ok, r_j, _ = ref.evaluate(blob)                  # re-evaluate, do not trust the stored file alone
    assert r_ok == exp["ok"] and (r_j.hex() if r_j else None) == exp["journal_hex"], name
    try:
        ok, journal, _ = cli.execute(blob)
    except cli.ZkError as e:
        if e.code != 2:                                  # host refuses malformed input before the guest runs
            raise
        ok, journal = False, None
    n += 1
    acc += ok
    if ok != exp["ok"] or (ok and journal.hex() != exp["journal_hex"]):
        bad.append(name)
print(f"vectors={n} guest_accept={acc} reference_accept={sum(json.loads(p.read_text())['ok'] for p in d.glob('*.expect.json'))} mismatches={len(bad)}")
for b in bad:
    print("MISMATCH", b)
sys.exit(1 if bad else 0)
