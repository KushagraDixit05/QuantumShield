import pytest

from demo import overheads as ov


def w(p, text):
    p.write_text(text)
    return p


@pytest.fixture
def results(tmp_path):
    w(tmp_path / "zk_bench.csv", "run,prove_s,verify_s,receipt_bytes\n0,400,0.2,3000\n1,300,0.3,3000\n")
    w(tmp_path / "phase3_fl.csv", "client,role,prove_s\n0,honest,380\n1,honest,610\n4,attacker x50,\n")
    w(tmp_path / "scenarios.csv", "attack,defence,mean_round_latency_ms,mean_update_env_bytes\n"
      "none,off,5.0,232\nnone,off,6.0,232\nnone,on,7.0,3574\nnone,on,9.0,3574\n")
    w(tmp_path / "zk_consensus.csv", "round,finalized_at_nodes,real_receipts_verified,round_latency_ms\n0,4,8,1500\n1,4,8,1700\n")
    return tmp_path


def test_parsers(results):
    b = ov.parse_zk_bench(results / "zk_bench.csv")
    assert b["prove_med"] == 350 and b["prove_max"] == 400 and b["receipt_bytes"] == 3000
    assert b["verify_ms"] == pytest.approx(250)
    f = ov.parse_phase3(results / "phase3_fl.csv")
    assert (f["n"], f["prove_min"], f["prove_max"]) == (2, 380, 610)
    s = ov.parse_scenarios(results / "scenarios.csv")
    assert s["off"]["latency_ms"] == 5.5 and s["on"]["env_bytes"] == 3574
    c = ov.parse_consensus(results / "zk_consensus.csv")
    assert c["latency_ms"] == 1600 and c["receipts"] == 8 and c["nodes"] == 4


def test_override(results):
    z = ov.load_zk(results, {"proof_bytes": 5, "prove_s": 1.0, "verify_ms": 2.0})
    assert z["bench"]["receipt_bytes"] == 5 and z["bench"]["verify_ms"] == 2.0


def test_table_complete(results):
    z = ov.load_zk(results)
    r = ov.measure(reps=2)
    md = ov.table(r, z)
    assert "pending" not in md.lower()
    for key in ("signature bytes / update, Ed25519", "ML-DSA-65", "hybrid", "sign time", "verify time", "proof size",
                "prove time", "per-round consensus latency", "bandwidth / update", "Hardware:", "simulated in-process",
                "not interactive", "1.6x", "zk_bench.csv", "phase3_fl.csv", "zk_consensus.csv", "scenarios.csv"):
        assert key in md, key
    assert f"{2410 * 8 + 232:,}" in md
