import hashlib
import shutil

import pytest

from backend import receipts
from backend.common import RES


@pytest.fixture(scope="module")
def rec(client):
    r = client.get("/api/receipts")
    assert r.status_code == 200, r.text
    return r.json()


def test_receipts_replay_only_and_verified(rec):
    assert rec["source"] == ["demo/results/zk/", "demo/results/zk_bench.md", "docs/zk_cost.md"]
    rs = rec["receipts"]
    assert len(rs) == 4 and {(r["round"], r["client"]) for r in rs} == {(0, 0), (0, 1), (1, 0), (1, 1)}
    for r in rs:
        data = (RES.parent.parent / r["path"]).read_bytes()
        assert r["id"] == hashlib.sha256(data).hexdigest()[:12] and r["bytes"] == len(data)
        assert r["replayed"] is True and "live" not in r and r["verified"] is True and r["verify_error"] is None
        assert r["journal_bytes"] == 146 and r["generated"].endswith("+00:00")
        assert r["label"].startswith(f"replayed from receipt {r['id']}, generated ") and "mtime" in r["label"]
        assert r["prove_s"] > 0 and r["cycles"] > 0 and r["peak_rss_mb"] > 0


def test_hardware_parsed(rec):
    hw = rec["hardware"]
    assert hw["gpu_used"] is False and hw["threads"] == 12 and hw["ram"] == "7.5 GiB"
    assert "i5-11260H" in hw["cpu"] and hw["zkvm"].startswith("risc0-zkvm") and hw["os"].startswith("Linux")


def test_zk_rounds(client):
    rows = client.get("/api/zk/rounds").json()["rounds"]
    st = {(r["round"], r["client"]): r for r in rows}
    assert st[(0, 0)]["status"] == "verified" and st[(1, 1)]["status"] == "verified"
    atk = st[(0, 4)]
    assert atk["status"] == "no_receipt" and "bad_proof:missing_proof_hash" in atk["reason"] and atk["receipt_id"] is None
    assert all(r["replayed"] is True for r in rows)


def test_tampered_receipt_is_not_verified(tmp_path, monkeypatch):
    d = tmp_path / "zk"
    d.mkdir()
    for ext in ("receipt", "journal"):
        shutil.copy(RES / "zk" / f"r0_c0.{ext}", d / f"r0_c0.{ext}")
    b = bytearray((d / "r0_c0.receipt").read_bytes())
    b[len(b) // 2] ^= 0xFF
    (d / "r0_c0.receipt").write_bytes(bytes(b))
    monkeypatch.setattr(receipts, "ZKDIR", d)
    monkeypatch.setattr(receipts, "_cache", {})
    r = receipts.load_receipts()["receipts"][0]
    assert r["verified"] is False and r["verify_error"]


def test_no_journal_means_null_not_true(tmp_path, monkeypatch):
    d = tmp_path / "zk"
    d.mkdir()
    shutil.copy(RES / "zk" / "r0_c0.receipt", d / "r0_c0.receipt")
    monkeypatch.setattr(receipts, "ZKDIR", d)
    monkeypatch.setattr(receipts, "_cache", {})
    r = receipts.load_receipts()["receipts"][0]
    assert r["verified"] is None and "expected public" in r["verify_error"] and r["round"] is None


def test_no_prover_is_referenced():
    import pathlib
    for p in pathlib.Path(receipts.__file__).parent.glob("*.py"):
        t = p.read_text()
        code = [l for l in t.splitlines() if not l.lstrip().startswith(("#", '"""'))]
        assert not any("prove_update(" in l or "client_prove(" in l or ".prove(" in l for l in code), p
