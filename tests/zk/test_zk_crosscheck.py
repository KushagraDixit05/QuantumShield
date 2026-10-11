"""Every vector in zk/bridge/vectors through the real guest executor (no proving) equals the reference
verdict and journal (the logic of zk/crosscheck.py, as a test)."""
import json
from pathlib import Path

import pytest

from fl import zk_reference as ref
from zk.bridge import cli

from conftest import ROOT, _need_binary

VEC = ROOT / "zk" / "bridge" / "vectors"
NAMES = sorted(f.name[: -len(".in.bin")] for f in VEC.glob("*.in.bin"))


def test_vector_count():
    assert len(NAMES) >= 86


@pytest.mark.parametrize("name", NAMES)
def test_guest_matches_reference(name):
    _need_binary()
    exp = json.loads((VEC / f"{name}.expect.json").read_text())
    blob = (VEC / f"{name}.in.bin").read_bytes()
    r_ok, r_j, r_reason = ref.evaluate(blob)
    assert r_ok == exp["ok"] and (r_j.hex() if r_j else None) == exp["journal_hex"], name
    try:
        ok, journal, _ = cli.execute(blob)
    except cli.ZkError as e:
        assert e.code == 2, e                        # host refuses malformed input before the guest runs
        ok, journal = False, None
    assert ok == exp["ok"], f"{name}: guest accept={ok}, reference says {exp['ok']} ({r_reason})"
    if ok:
        assert journal.hex() == exp["journal_hex"]
