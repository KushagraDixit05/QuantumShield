"""Bridge plumbing. The fake qs-zk below is TEST PLUMBING that mimics exit codes; it verifies nothing.
Real-binary tests use `qs-zk execute` only (no proving)."""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from fl import zk_reference as zr
from zk.bridge import cli
from zk.bridge import vectors as V

FAKE = """#!{py}
import sys, json
# TEST PLUMBING ONLY: mimics qs-zk exit codes from the env var FAKE_EXIT; checks and proves nothing.
import os
args = sys.argv[1:]
code = int(os.environ.get("FAKE_EXIT", "0"))
def opt(n):
    return args[args.index(n) + 1]
if code:
    sys.stderr.write("fake failure\\n"); sys.exit(code)
if args[0] == "execute":
    open(opt("--journal"), "wb").write(open(opt("--input"), "rb").read()[:146])
    json.dump({{"cycles": 1}}, open(opt("--stats"), "w"))
elif args[0] == "prove":
    open(opt("--receipt"), "wb").write(b"receipt")
    open(opt("--journal"), "wb").write(open(opt("--input"), "rb").read()[:146])
    json.dump({{"prove_s": 0.0, "po2": int(opt("--po2")), "kind": opt("--kind")}}, open(opt("--stats"), "w"))
elif args[0] == "image-id":
    print("ab" * 32)
"""


@pytest.fixture
def fake(tmp_path, monkeypatch):
    p = tmp_path / "qs-zk-fake"
    p.write_text(FAKE.format(py=sys.executable))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("QS_ZK_BIN", str(p))
    return p


def test_missing_binary(monkeypatch, tmp_path):
    monkeypatch.setenv("QS_ZK_BIN", str(tmp_path / "nope"))
    with pytest.raises(cli.ZkError) as e:
        cli.image_id()
    assert e.value.reason == "binary_missing"
    assert cli.verify_receipt(b"x", bytes(146)) == (False, "binary_missing")


@pytest.mark.parametrize("code,reason", [(4, "receipt_invalid"), (5, "journal_mismatch"), (3, "guest_failed"),
                                         (2, "bad_input"), (6, "refused"), (9, "error_9")])
def test_verify_exit_code_mapping(fake, monkeypatch, code, reason):
    monkeypatch.setenv("FAKE_EXIT", str(code))
    assert cli.verify_receipt(b"r", bytes(146)) == (False, reason)


def test_verify_ok(fake):
    assert cli.verify_receipt(b"r", bytes(146)) == (True, "ok")


def test_execute_and_prove_plumbing(fake, tmp_path, monkeypatch):
    blob = b"QSZK" + bytes(300)
    ok, j, st = cli.execute(blob)
    assert ok and j == blob[:146] and st == {"cycles": 1}
    stats = cli.prove_update(blob, tmp_path / "x" / "r.bin", tmp_path / "x" / "j.bin", po2=17, kind="succinct")
    assert stats["po2"] == 17 and stats["kind"] == "succinct"
    assert (tmp_path / "x" / "r.bin").read_bytes() == b"receipt"
    monkeypatch.setenv("FAKE_EXIT", "3")
    ok, j, st = cli.execute(blob)
    assert not ok and j is None
    with pytest.raises(cli.ZkError) as e:
        cli.prove_update(blob, tmp_path / "r2", tmp_path / "j2")
    assert e.value.reason == "guest_failed"
    monkeypatch.setenv("FAKE_EXIT", "2")
    with pytest.raises(cli.ZkError) as e:
        cli.execute(blob)
    assert e.value.reason == "bad_input"


def test_client_blob_uses_local_train_and_is_accepted_by_reference(fake):
    import numpy as np

    from fl import client as flc
    from fl import data, merkle, model
    from fl import fixedpoint as fx
    from pq import envelope as ev
    clients, _ = data.load(0, 5)
    ds, w = clients[2], model.init(0)
    tree = merkle.MerkleTree(ds.X, ds.y)
    lr = int(fx.to_fx(0.3))
    nonce = ev.make_nonce(0, 1, 2)
    blob, delta = cli.client_blob(w, ds, 1, 2, 0, 2, 4, lr, fx.bound_sq(1.2664), nonce, tree)
    idx = flc.sample_indices(0, 1, 2, 2, 4, len(ds))
    assert np.array_equal(delta, flc.local_train(w, ds, idx, lr))
    ok, j, why = zr.evaluate(blob)
    assert ok, why
    p = zr.parse_input(blob)
    assert p["C"] == ev.commit(delta, nonce) and p["R"] == tree.root and p["h_w"] == ev.model_hash(w)
    res = cli.client_prove(w, ds, 1, 2, 0, 2, 4, lr, fx.bound_sq(1.2664), nonce, tree,
                           "/tmp/_nope_r.bin", "/tmp/_nope_j.bin")
    assert res["commitment"] == p["C"]
    for f in ("/tmp/_nope_r.bin", "/tmp/_nope_j.bin"):
        os.path.exists(f) and os.remove(f)


# ---------------------------------------------------------------- real binary, execute only
REAL = Path(os.environ.get("QS_ZK_BIN") or cli.DEFAULT_BIN)
# Known guest/reference differences, see docs/zk_status/agent_c.md (relation 2 must have K = batch = 0)
KNOWN_GUEST_ACCEPTS = set()  # v1.3: guest now enforces K = batch = 0 for relation 2


@pytest.mark.skipif(not REAL.exists(), reason="qs-zk binary not built")
def test_real_binary_execute_agrees_with_reference():
    gen = V.generate("configs/phase3.yaml")
    bad = []
    for name, (blob, meta) in gen.vectors.items():
        try:
            ok, j, _ = cli.execute(blob)
        except cli.ZkError as e:
            assert e.reason == "bad_input", (name, e)  # host refuses malformed files before the guest runs
            ok, j = False, None
        if ok != meta["ok"] or (j is not None and j.hex() != meta["journal_hex"]):
            bad.append(name)
    assert set(bad) <= KNOWN_GUEST_ACCEPTS, bad
