"""backend.runner mirrors demo.run_demo.run_scenario; these tests detect drift between the two."""
import pytest

from backend import runner
from backend.run_queue import base_cfg
from demo import run_demo


def _cmp(attack, defence_on, rounds, seed=0):
    cfg = base_cfg()
    cfg["rounds"] = rounds
    ref = run_demo.run_scenario(cfg, attack, defence_on, seed)
    mine = runner.run_seed(cfg, attack, defence_on, "fedavg", seed)
    return ref, mine


@pytest.mark.parametrize("attack,defence_on", [("scaled", True), ("none", False), ("replay", True), ("forged", True)])
def test_fedavg_matches_run_scenario(attack, defence_on):
    ref, mine = _cmp(attack, defence_on, 3)
    assert mine["acc"] == ref["acc"]                       # identical floats, no tolerance
    assert mine["diverged_round"] == ref["diverged_round"]
    assert mine["accepted"] == ref["accepted"]
    assert mine["rejects"] == ref["rejects"]
    assert mine["finalized_rounds"] == ref["finalized_rounds"]


def test_diverged_matches_with_null_instead_of_zero():
    ref, mine = _cmp("scaled", False, 9)
    assert ref["diverged_round"] is not None and mine["diverged_round"] == ref["diverged_round"]
    d = mine["diverged_round"]
    assert [a if a is not None else 0.0 for a in mine["acc"]] == ref["acc"]
    assert all(a is None for a in mine["acc"][d + 1:]) and 0.0 not in mine["acc"]


def test_aggregator_is_really_used():
    cfg = base_cfg()
    cfg["rounds"] = 2
    fed = runner.run_seed(cfg, "scaled", False, "fedavg", 0)
    med = runner.run_seed(cfg, "scaled", False, "median", 0)
    assert fed["acc"] != med["acc"]


def test_no_quorum_is_not_in_quorum_and_not_diverged(monkeypatch):
    """Two silent aggregators -> only 2 votes < 2f+1: not_in_quorum (client null), not a divergence."""
    real = runner.Node

    def faulty(nid, *a, **kw):
        return real(nid, *a, fault_mode="silent" if nid >= 2 else "honest", **kw)
    monkeypatch.setattr(runner, "Node", faulty)
    cfg = base_cfg()
    cfg["rounds"] = 3
    evs = []
    res = runner.run_seed(cfg, "none", False, "fedavg", 0, emit=evs.append)
    rounds = [e for e in evs if e["type"] == "round"]
    assert len(rounds) == 1 and rounds[0]["diverged"] is False and rounds[0]["accuracy"] is None
    assert rounds[0]["consensus"] == {"leader": 0, "votes": 2, "quorum": 3, "finalized": False}
    q = [r for r in rounds[0]["rejections"] if r["reason"] == "not_in_quorum"]
    assert len(q) == 1 and q[0]["client"] is None and q[0]["gate"] == "consensus"
    assert res["diverged_round"] is None and res["stopped_round"] == 0
    assert runner.seed_summary(0, res)["final_accuracy"] is None
