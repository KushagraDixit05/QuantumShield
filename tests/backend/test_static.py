"""Health, scenarios, stored results, limitations, overheads (ported from the old tests/test_backend.py plus new cases)."""
import re

import pytest

from backend import limitations, results
from backend.common import ROOT


def test_health(client):
    h = client.get("/api/health").json()
    assert h["ok"] is True and h["live_zk_enabled"] is False
    assert isinstance(h["prover_lock_held"], bool) and isinstance(h["queue_length"], int)


def test_cors(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:3001"):
        r = client.get("/api/health", headers={"Origin": origin})
        assert r.headers["access-control-allow-origin"] == origin
    r = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_scenarios(client):
    s = client.get("/api/scenarios").json()
    assert [x["id"] for x in s["scenarios"]] == ["A", "B", "C"]
    assert s["aggregators"] == ["fedavg", "norm_filter", "median", "clip"]
    assert s["live_zk_enabled"] is False and s["default_seeds"] == [0, 1, 2, 3, 4] and s["default_rounds"] == 10


@pytest.mark.parametrize("name", [n for n in results.NAMES if n != "attack_matrix"])
def test_results_files(client, name):
    r = client.get(f"/api/results/{name}")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["name"] == name and b["source"] and all(s.startswith("demo/results/") for s in b["source"])
    if name in results.CSV:
        assert b["rows"] and set(b["columns"]) == set(b["rows"][0])
    if name == "scenarios_curves":
        assert set(b["json"]["scenarios"]) == {"A", "B", "C"}
    if name == "overheads":
        assert "|" in b["markdown"]


def test_results_parsing_and_blank_is_null(client):
    rows = client.get("/api/results/scenarios").json()["rows"]
    first = rows[0]
    assert isinstance(first["seed"], int) and isinstance(first["final_acc"], float)
    assert first["diverged_round"] is None                 # blank cell, not "" and not 0
    assert any(isinstance(r["diverged_round"], int) for r in rows)


def test_d012_text_comes_from_decisions_md(client):
    note = client.get("/api/results/scenarios").json()["diverged_note"]
    line = next(l for l in (ROOT / "docs/decisions.md").read_text().splitlines() if l.startswith("- D-012"))
    assert note["decision"] == "D-012" and note["text"] == line.split(" ", 2)[2]


def test_attack_matrix(client):
    b = client.get("/api/results/attack_matrix").json()
    assert "computed" in b["source"][0] and "scenarios.csv" in b["source"][0] and b["diverged_note"]["decision"] == "D-012"
    cell = {(r["attack"], r["defence"]): r for r in b["rows"]}
    assert len(cell) == 8
    div = [r for r in b["rows"] if r["n_diverged"]]
    assert div, "stored results contain diverged cells"
    for r in div:
        assert r["diverged"] == f"{r['n_diverged']} of {r['n_seeds']}" and r["accuracy_is_plain"] is False
        assert r["mean_final_acc"] != 0.0                      # never the 0.0 convention
    clean = cell[("none", "off")]
    assert clean["diverged"] is None and clean["accuracy_is_plain"] and 0.9 < clean["mean_final_acc"] < 1.0


def test_results_unknown_and_traversal(client):
    for bad in ("nope", "..%2Fconfig", "%2e%2e%2f%2e%2e%2fetc%2fpasswd", "scenarios.csv"):
        assert client.get(f"/api/results/{bad}").status_code == 404


def test_missing_file_is_404(client, monkeypatch, tmp_path):
    monkeypatch.setattr(results, "RES", tmp_path)
    r = client.get("/api/results/scenarios")
    assert r.status_code == 404 and "not found" in r.json()["detail"]


def test_limitations_19_items(client):
    b = client.get("/api/limitations").json()
    assert b["source"] == "docs/limitations.md"
    assert len(b["sections"]) == 5
    items = [i for s in b["sections"] for i in s["items"]]
    assert len(items) == 19 and [i["n"] for i in items] == list(range(1, 20))
    assert [s["title"] for s in b["sections"]][0] == "Privacy"


def test_limitations_parser_is_not_retyped():
    secs = limitations.parse("## A\n1. x\n2. y\n## B\n3. z\n")
    assert [(s["title"], [i["n"] for i in s["items"]]) for s in secs] == [("A", [1, 2]), ("B", [3])]


def test_overheads(client):
    b = client.get("/api/overheads").json()
    assert b["signatures"]["rows"] and b["envelope"]["rows"] and b["throughput"]["rows"] and b["zk"]["rows"]
    assert b["zk"]["source"] == "demo/results/zk_bench.csv" and b["round"]["source"] == "demo/results/scenarios.csv"
    assert "|" in b["markdown"]["text"] and b["hardware"]["cpu"]
    assert re.search(r"i5", b["hardware"]["cpu"])
