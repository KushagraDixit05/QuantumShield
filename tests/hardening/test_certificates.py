"""Certificate hardening (Agent X). A certificate = the round's signed votes (docs/ui_issues.md UI-002).
Every tampered certificate must come back valid=false (or quorum_met=false where the documented semantics say so).
Semantics (docs/api_contract.md): quorum_met = at least 3 distinct nodes with verifying votes for one hash;
valid = quorum_met AND every supplied vote verifies. Independent of tests/backend fixtures."""
import copy
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import run_queue
from backend.main import app

ROOT = Path(__file__).resolve().parents[2]
ROUNDS = 6   # epoch_rounds=5: round 5 is signed with epoch-1 keys (key rotation); no proving, a few seconds


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _run(client, seed, rounds):
    r = client.post("/api/runs", json={"scenario": "C", "aggregator": "fedavg", "seeds": [seed], "rounds": rounds})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    with client.stream("GET", f"/api/runs/{rid}/stream") as s:
        assert s.status_code == 200
        for _ in s.iter_lines():
            pass
    return rid


@pytest.fixture(scope="module")
def rid(client):
    return _run(client, 0, ROUNDS)


@pytest.fixture(scope="module")
def other_rid(client):
    return _run(client, 1, 2)


def cert(client, rid, rnd=0):
    r = client.get(f"/api/certificates/{rid}/{rnd}")
    assert r.status_code == 200, r.text
    return r.json()


def verify(client, body):
    r = client.post("/api/certificates/verify", json=body)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["public_keys_only"] is True
    return b


def flip_hex(h, pos=-2):
    return h[:pos] + ("00" if h[pos:][:2] != "00" else "ff") + (h[pos + 2:] if pos + 2 else "")


def test_untouched_certificate_valid_for_every_round(client, rid):
    for rnd in range(ROUNDS):
        c = cert(client, rid, rnd)
        assert len(c["votes"]) == 4 and c["round"] == rnd and c["run_id"] == rid
        b = verify(client, {"certificate": c})
        assert b["valid"] is True and b["quorum_met"] is True, (rnd, b)
        assert [x["node"] for x in b["checked"]] == [0, 1, 2, 3] and all(x["ok"] and x["reason"] == "ok" for x in b["checked"])
        # the stored-round form gives the identical answer
        assert verify(client, {"run_id": rid, "round": rnd}) == b


def test_signature_flipped(client, rid):
    c = cert(client, rid)
    s = c["votes"][2]["sigs"][0]["sig"]
    c["votes"][2]["sigs"][0]["sig"] = s[:-2] + ("00" if s[-2:] != "00" else "ff")
    b = verify(client, {"certificate": c})
    assert b["valid"] is False
    bad = [x for x in b["checked"] if not x["ok"]]
    assert [x["node"] for x in bad] == [2] and bad[0]["reason"] == "bad_signature"
    assert b["quorum_met"] is True   # 3 good votes remain; whole certificate still invalid


def test_second_signature_of_hybrid_flipped(client, rid):
    c = cert(client, rid)
    assert len(c["votes"][0]["sigs"]) == 2    # Ed25519 + ML-DSA-65
    s = c["votes"][0]["sigs"][1]["sig"]
    c["votes"][0]["sigs"][1]["sig"] = s[:-2] + ("00" if s[-2:] != "00" else "ff")
    b = verify(client, {"certificate": c})
    assert b["valid"] is False and not b["checked"][0]["ok"]


def test_payload_hash_changed(client, rid):
    c = cert(client, rid)
    p = bytearray(bytes.fromhex(c["votes"][0]["payload"]))
    p[-40] ^= 1                                  # inside h_next (voted model hash)
    c["votes"][0]["payload"] = bytes(p).hex()
    b = verify(client, {"certificate": c})
    assert b["valid"] is False and b["checked"][0]["ok"] is False and b["checked"][0]["node"] == 0
    assert all(x["ok"] for x in b["checked"][1:])


def test_all_votes_payload_changed_not_valid_nor_quorum(client, rid):
    c = cert(client, rid)
    for v in c["votes"]:
        p = bytearray(bytes.fromhex(v["payload"]))
        p[-40] ^= 1
        v["payload"] = bytes(p).hex()
    b = verify(client, {"certificate": c})
    assert b["valid"] is False and b["quorum_met"] is False and not any(x["ok"] for x in b["checked"])


def test_fewer_than_three_votes(client, rid):
    c = cert(client, rid)
    c["votes"] = c["votes"][:2]
    b = verify(client, {"certificate": c})
    assert b["quorum_met"] is False and b["valid"] is False and all(x["ok"] for x in b["checked"])
    c["votes"] = c["votes"][:1]
    b = verify(client, {"certificate": c})
    assert b["quorum_met"] is False and b["valid"] is False
    c["votes"] = []
    b = verify(client, {"certificate": c})
    assert b["quorum_met"] is False and b["valid"] is False and b["checked"] == []


def test_three_votes_is_exactly_quorum(client, rid):
    c = cert(client, rid)
    c["votes"] = c["votes"][1:]
    b = verify(client, {"certificate": c})
    assert b["quorum_met"] is True and b["valid"] is True


def test_same_voter_duplicated_to_fake_three_votes(client, rid):
    c = cert(client, rid)
    c["votes"] = [copy.deepcopy(c["votes"][0]) for _ in range(3)]
    b = verify(client, {"certificate": c})
    # first copy is a genuine signature; the verifier flags the repeats as replayed nonces
    assert [(x["node"], x["ok"]) for x in b["checked"]] == [(0, True), (0, False), (0, False)]
    assert {x["reason"] for x in b["checked"][1:]} == {"replayed_nonce"}
    assert b["quorum_met"] is False and b["valid"] is False   # one distinct voter is not a quorum
    c["votes"] = [copy.deepcopy(c["votes"][0]) for _ in range(10)]
    b = verify(client, {"certificate": c})
    assert b["quorum_met"] is False and b["valid"] is False


def test_two_voters_duplicated_to_fake_three(client, rid):
    v = cert(client, rid)["votes"]
    c = cert(client, rid)
    c["votes"] = [v[0], v[1], v[1]]
    b = verify(client, {"certificate": c})
    assert b["quorum_met"] is False and b["valid"] is False


def test_vote_from_unknown_node_id(client, rid):
    # relabel a genuine vote as node 9 (not a member of the 4-node set)
    c = cert(client, rid)
    c["votes"][3]["node"] = 9
    b = verify(client, {"certificate": c})
    assert b["valid"] is False and b["checked"][3]["ok"] is False and b["checked"][3]["node"] == 9
    # a 4th vote 'from' node 9 added to only two genuine ones does not reach quorum
    c2 = cert(client, rid)
    extra = copy.deepcopy(c2["votes"][0])
    extra["node"] = 9
    c2["votes"] = c2["votes"][:2] + [extra]
    b2 = verify(client, {"certificate": c2})
    assert b2["quorum_met"] is False and b2["valid"] is False


def test_payload_agg_id_rewritten_to_unknown_node(client, rid):
    c = cert(client, rid)
    p = bytearray(bytes.fromhex(c["votes"][0]["payload"]))
    p[7] = 9                                           # agg_id field is the 4 bytes after v,k,round (little/any endian: low byte)
    c["votes"][0]["payload"] = bytes(p).hex()
    c["votes"][0]["node"] = 9
    b = verify(client, {"certificate": c})
    assert b["valid"] is False and b["checked"][0]["ok"] is False


def test_round_field_changed_to_another_round(client, rid):
    for src, dst in ((0, 1), (1, 0), (2, 5), (5, 0)):
        c = cert(client, rid, src)
        c["round"] = dst
        b = verify(client, {"certificate": c})
        assert b["valid"] is False and b["quorum_met"] is False, (src, dst, b)
        assert not any(x["ok"] for x in b["checked"])


def test_votes_from_two_rounds_mixed(client, rid):
    c0, c1 = cert(client, rid, 0), cert(client, rid, 1)
    c0["votes"] = c0["votes"][:2] + c1["votes"][2:]
    b = verify(client, {"certificate": c0})
    assert b["valid"] is False and b["quorum_met"] is False


def test_certificate_from_different_run_pasted_under_this_run_id(client, rid, other_rid):
    foreign = cert(client, other_rid, 0)               # seed 1 run: different registry keys
    assert verify(client, {"certificate": foreign})["valid"] is True      # control: valid under its own run
    foreign["run_id"] = rid                            # now claim it belongs to the seed-0 run
    foreign.pop("seed", None)
    b = verify(client, {"certificate": foreign})
    assert b["valid"] is False and b["quorum_met"] is False and not any(x["ok"] for x in b["checked"])
    # the opposite direction
    mine = cert(client, rid, 0)
    mine["run_id"] = other_rid
    mine.pop("seed", None)
    b = verify(client, {"certificate": mine})
    assert b["valid"] is False and b["quorum_met"] is False


def test_unknown_run_id_in_pasted_certificate(client, rid):
    c = cert(client, rid)
    c["run_id"] = "does-not-exist"
    r = client.post("/api/certificates/verify", json={"certificate": c})
    assert r.status_code == 404          # documented: the registry comes from the run; no run, no verification


def test_keys_in_the_paste_are_ignored(client, rid):
    """Attacker signs fake votes with its own keys and ships its public registry inside the paste."""
    from pq import envelope as ev
    from pq import registry as rg
    snap = run_queue.QUEUE.jobs[rid].states[0]["registry"]
    mine = rg.KeyRegistry(snap["n"]["client"], snap["n"]["agg"], snap["algs"], seed=987654, epoch_rounds=snap["epoch_rounds"])
    assert mine.pks != {k: bytes.fromhex(v) for k, v in snap["pks"].items()}
    good = cert(client, rid)
    fake_hash = bytes(range(32))
    votes = []
    for node in range(4):
        env = ev.sign_payload(mine, "agg", node, snap["algs"], ev.pack_vote(0, node, fake_hash, bytes(32), bytes(32)))
        votes.append({"node": node, "payload": env.payload.hex(),
                      "sigs": [{"alg": a, "key_id": k, "sig": s.hex()} for a, k, s in env.sigs]})
    # sanity: these votes ARE valid under the attacker's own registry, so only the key source can reject them
    from pq import policy
    ver = policy.Verifier(rg.KeyRegistry.from_snapshot(mine.snapshot()), "hybrid", "ML-DSA-65", "Ed25519")
    ver.begin_round(0, b"")
    assert all(ver.verify_vote(ev.Envelope(bytes.fromhex(v["payload"]), [(s["alg"], s["key_id"], bytes.fromhex(s["sig"])) for s in v["sigs"]]))[0]
               for v in votes)
    forged = dict(good, votes=votes)
    attacker_snapshot = mine.snapshot()
    body = {"certificate": dict(forged, registry=attacker_snapshot, public_keys=attacker_snapshot["pks"], pks=attacker_snapshot["pks"]),
            "registry": attacker_snapshot, "public_keys": attacker_snapshot["pks"], "pks": attacker_snapshot["pks"]}
    r = client.post("/api/certificates/verify", json=body)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["valid"] is False and b["quorum_met"] is False and not any(x["ok"] for x in b["checked"]), b
    assert b["public_keys_only"] is True
    # extra key material inside each vote's sig dicts must not be consulted either
    for v in forged["votes"]:
        for s in v["sigs"]:
            s["pk"] = attacker_snapshot["pks"][s["key_id"]].__str__()
    r2 = client.post("/api/certificates/verify", json={"certificate": forged})
    assert r2.status_code == 200 and r2.json()["valid"] is False and r2.json()["quorum_met"] is False
    # control: the genuine certificate with the same junk fields attached stays valid
    ok = client.post("/api/certificates/verify", json={"certificate": dict(good, registry=attacker_snapshot), "pks": attacker_snapshot["pks"]})
    assert ok.status_code == 200 and ok.json()["valid"] is True


def test_key_rotation_epoch_round(client, rid):
    # rounds 0-4 use epoch-0 keys, round 5 epoch-1 keys; both verify and cross-labelling fails
    reg = run_queue.QUEUE.jobs[rid].states[0]["registry"]
    assert reg["epoch"] >= 1
    for rnd in (4, 5):
        assert verify(client, {"certificate": cert(client, rid, rnd)})["valid"] is True
    c = cert(client, rid, 5)
    c["round"] = 4                                      # epoch-1 signatures under an epoch-0 round label
    b = verify(client, {"certificate": c})
    assert b["valid"] is False and b["quorum_met"] is False
    c = cert(client, rid, 4)
    c["round"] = 5
    b = verify(client, {"certificate": c})
    assert b["valid"] is False and b["quorum_met"] is False
    # key ids in a round-5 certificate name epoch 1
    assert all("1" in s["key_id"] for v in cert(client, rid, 5)["votes"] for s in v["sigs"])


def test_malformed_input_reported_not_crashed(client, rid):
    c = cert(client, rid)
    c["votes"][0]["payload"] = "zz"
    b = verify(client, {"certificate": c})
    assert b["checked"][0]["reason"] == "malformed" and b["valid"] is False
    c = cert(client, rid)
    c["votes"][1]["sigs"] = []
    b = verify(client, {"certificate": c})
    assert b["valid"] is False and b["checked"][1]["ok"] is False


def test_handler_never_references_secret_keys():
    """Source-level check: neither the certificate module nor the two certificate handlers touch secret key material."""
    cert_src = (ROOT / "backend" / "certificates.py").read_text()
    code = re.sub(r'""".*?"""', "", cert_src, flags=re.S)     # drop the docstring that says 'No secret key is read'
    code = re.sub(r"#.*", "", code)
    assert not re.search(r"\b_?sk\b|secret", code, flags=re.I), "backend/certificates.py references secret key material"
    assert "secret_key" not in code and "_sk" not in code
    assert "KeyRegistry.from_snapshot" in code or "rg.KeyRegistry.from_snapshot" in code
    main_src = (ROOT / "backend" / "main.py").read_text()
    m = re.search(r'@app\.get\("/api/certificates/\{run_id\}/\{round\}".*?(?=@app\.get\("/api/limitations")', main_src, flags=re.S)
    assert m, "certificate handlers not found in backend/main.py"
    handlers = m.group(0)
    assert not re.search(r"\bsk\b|_sk\b|secret", handlers, flags=re.I)


def test_response_and_snapshot_carry_no_secret_fields(client, rid):
    snap = run_queue.QUEUE.jobs[rid].states[0]["registry"]
    assert not re.search(r"\bsk\b|_sk|secret", json.dumps(sorted(snap)), flags=re.I)
    for body in ({"run_id": rid, "round": 0}, {"certificate": cert(client, rid)}):
        txt = client.post("/api/certificates/verify", json=body).text
        assert not re.search(r"secret|\"sk\"|_sk", txt, flags=re.I)
    assert not re.search(r"secret|\"sk\"|_sk", json.dumps(cert(client, rid)), flags=re.I)
