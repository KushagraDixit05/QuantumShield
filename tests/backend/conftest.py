import json
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def read_events(client, run_id):
    out = []
    with client.stream("GET", f"/api/runs/{run_id}/stream") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


def start(client, **body):
    r = client.post("/api/runs", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture(scope="session")
def run_c(client):
    """Scenario C (scaled attacker, defence on), fedavg, seed 0, 2 rounds."""
    rid = start(client, scenario="C", aggregator="fedavg", seeds=[0], rounds=2)
    return rid, read_events(client, rid)


@pytest.fixture(scope="session")
def run_b(client):
    """Scenario B (scaled attacker, no defence), plain FedAvg: diverges (D-012) within 10 rounds."""
    rid = start(client, scenario="B", aggregator="fedavg", seeds=[0], rounds=10)
    return rid, read_events(client, rid)
