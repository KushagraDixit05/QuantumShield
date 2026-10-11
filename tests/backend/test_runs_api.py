import fcntl
import time

import pytest

from backend import common, run_queue
from tests.backend.conftest import read_events, start


def test_scenario_c_events(run_c):
    rid, evs = run_c
    kinds = [e["type"] for e in evs]
    assert kinds[0] == "queued" and "started" in kinds and kinds[-1] == "done" and kinds.count("round") == 2
    st = next(e for e in evs if e["type"] == "started")
    assert (st["seed"], st["attack"], st["defence"], st["aggregator"], st["rounds"]) == (0, "scaled", "on", "fedavg", 2)
    r0 = next(e for e in evs if e["type"] == "round")
    assert r0["diverged"] is False and 0 < r0["accuracy"] < 1 and r0["model_hash"]
    assert r0["accepted"] == [0, 1, 2, 3] and r0["accepted_count"] == 4 and r0["rejected_count"] == 1
    assert r0["rejections"] == [{"round": 0, "client": 4, "reason": "norm_bound_exceeded",
                                 "raw_reason": "norm_bound_exceeded", "gate": "plaintext_norm_gate"}]
    assert r0["consensus"] == {"leader": 0, "votes": 4, "quorum": 3, "finalized": True}
    done = evs[-1]
    assert done["results"][0]["final_accuracy"] is not None and done["results"][0]["diverged_round"] is None
    assert done["source"] == "computed live by backend.runner (mirrors demo/run_demo.py:run_scenario)"


def test_reconnect_replays_from_start(client, run_c):
    rid, evs = run_c
    assert read_events(client, rid) == evs


def test_diverged_round_is_null_never_zero(run_b):
    rid, evs = run_b
    rounds = [e for e in evs if e["type"] == "round"]
    div = [e for e in rounds if e["diverged"]]
    assert len(div) == 1 and div[0]["accuracy"] is None and rounds[-1] is div[0]
    assert all(e["accuracy"] != 0.0 for e in rounds)
    sd = next(e for e in evs if e["type"] == "seed_done")
    assert sd["final_accuracy"] is None and sd["diverged_round"] == div[0]["round"]
    assert "D-012" in sd["convention_note"] and "int64" in sd["convention_note"]
    assert not any(r["reason"] == "not_in_quorum" for e in rounds for r in e["rejections"])


def test_multi_seed_and_aggregator(client):
    rid = start(client, attack="none", defence="off", aggregator="median", seeds=[0, 1], rounds=1)
    evs = read_events(client, rid)
    assert [e["seed"] for e in evs if e["type"] == "started"] == [0, 1]
    assert len(evs[-1]["results"]) == 2 and evs[-1]["results"][0]["final_accuracy"] is not None


@pytest.mark.parametrize("body", [
    dict(scenario="C", seeds=[0], live_zk=True),
    dict(attack="bogus", defence="on", seeds=[0]),
    dict(attack="none", seeds=[0]),
    dict(seeds=[0]),
    dict(scenario="A", seeds=[]),
    dict(scenario="A", seeds=[0, 1, 2, 3, 4, 5]),
    dict(scenario="A", seeds=[-1]),
    dict(scenario="A", seeds=[10**6 + 1]),
    dict(scenario="A", seeds=[0], rounds=0),
    dict(scenario="A", seeds=[0], rounds=51),
    dict(scenario="A", seeds=[0], aggregator="krum"),
])
def test_bad_requests_are_422(client, body):
    assert client.post("/api/runs", json=body).status_code == 422


def test_live_zk_message(client):
    r = client.post("/api/runs", json=dict(scenario="A", seeds=[0], live_zk=True))
    assert r.status_code == 422 and r.json()["detail"] == "live ZK proving is disabled on this server"


def test_unknown_run(client):
    for p in ("/api/runs/nope/stream", "/api/consensus/nope"):
        assert client.get(p).status_code == 404


def test_waits_while_prover_lock_held_and_emits_queued(client, monkeypatch):
    calls = {"n": 0}

    def held():
        calls["n"] += 1
        return calls["n"] <= 2
    monkeypatch.setattr(common, "prover_lock_held", held)
    monkeypatch.setattr(run_queue, "LOCK_POLL_S", 0.01)
    rid = start(client, attack="none", defence="off", seeds=[0], rounds=1)
    evs = read_events(client, rid)
    assert [e["type"] for e in evs].count("queued") == 3 and evs[-1]["type"] == "done"
    assert calls["n"] >= 3


def test_lock_probe_sees_a_real_flock(tmp_path, monkeypatch):
    lock = tmp_path / "lock"
    lock.write_text("")
    monkeypatch.setattr(common, "LOCK_PATH", lock)
    assert common.prover_lock_held() is False
    with open(lock) as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        assert common.prover_lock_held() is True
    assert common.prover_lock_held() is False
    monkeypatch.setattr(common, "LOCK_PATH", tmp_path / "missing")
    assert common.prover_lock_held() is False


def test_jobs_run_one_at_a_time(client):
    a = client.post("/api/runs", json=dict(scenario="C", seeds=[0], rounds=2)).json()
    b = client.post("/api/runs", json=dict(scenario="A", seeds=[0], rounds=1)).json()
    assert b["queue_position"] >= 1 and a["id"] != b["id"]
    ea, eb = read_events(client, a["id"]), read_events(client, b["id"])
    assert ea[-1]["type"] == eb[-1]["type"] == "done"
