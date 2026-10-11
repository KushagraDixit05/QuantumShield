import copy

import pytest

from backend import certificates


def test_consensus_view(client, run_c):
    rid, _ = run_c
    b = client.get(f"/api/consensus/{rid}").json()
    assert (b["n"], b["f"], b["quorum"], b["leader"]) == (4, 1, 3, 0)
    assert b["leader_policy"] == "fixed (no rotation)" and b["view_changes"] == [] and "D-020" in b["view_changes_note"]
    assert [r["round"] for r in b["rounds"]] == [0, 1]
    r0 = b["rounds"][0]
    assert r0["finalized"] and r0["equivocators"] == [] and r0["bad_votes"] == 0 and len(r0["certificate_id"]) == 12
    assert [v["node"] for v in r0["votes"]] == [0, 1, 2, 3]
    assert all(v["valid"] and v["signer_alg"] == "Ed25519+ML-DSA-65" and v["hash"] == r0["model_hash"] for v in r0["votes"])
    assert "raw_votes" not in r0


def test_consensus_seed_param(client, run_c):
    rid, _ = run_c
    assert client.get(f"/api/consensus/{rid}?seed=0").status_code == 200
    assert client.get(f"/api/consensus/{rid}?seed=9").status_code == 404


def test_valid_certificate_passes(client, run_c):
    rid, _ = run_c
    r = client.post("/api/certificates/verify", json={"run_id": rid, "round": 0})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["valid"] and b["quorum_met"] and b["public_keys_only"] is True
    assert b["source"] == "pq/policy.py Verifier.verify_vote"
    assert [c["node"] for c in b["checked"]] == [0, 1, 2, 3] and all(c["ok"] and c["reason"] == "ok" for c in b["checked"])


def test_round_after_key_rotation_also_verifies(client):
    from tests.backend.conftest import read_events, start
    rid = start(client, attack="none", defence="on", seeds=[0], rounds=6)       # epoch_rounds=5: round 5 uses epoch 1 keys
    read_events(client, rid)
    for rnd in (0, 5):
        assert client.post("/api/certificates/verify", json={"run_id": rid, "round": rnd}).json()["valid"] is True


def _cert(client, rid, rnd=0):
    return client.get(f"/api/certificates/{rid}/{rnd}").json()


def _verify(client, cert):
    r = client.post("/api/certificates/verify", json={"certificate": cert})
    assert r.status_code == 200, r.text
    return r.json()


def test_pasted_certificate_roundtrip(client, run_c):
    rid, _ = run_c
    assert _verify(client, _cert(client, rid))["valid"] is True


def test_tampered_signature_fails(client, run_c):
    rid, _ = run_c
    cert = _cert(client, rid)
    sig = cert["votes"][1]["sigs"][0]["sig"]
    cert["votes"][1]["sigs"][0]["sig"] = sig[:-2] + ("00" if sig[-2:] != "00" else "ff")
    b = _verify(client, cert)
    assert b["valid"] is False
    bad = [c for c in b["checked"] if not c["ok"]]
    assert [c["node"] for c in bad] == [1] and bad[0]["reason"] == "bad_signature"
    assert b["quorum_met"] is True                        # 3 of 4 still valid; the certificate as a whole is not


def test_tampered_payload_fails(client, run_c):
    rid, _ = run_c
    cert = _cert(client, rid)
    p = bytearray(bytes.fromhex(cert["votes"][0]["payload"]))
    p[-40] ^= 1                                           # inside the accepted-set hash
    cert["votes"][0]["payload"] = bytes(p).hex()
    b = _verify(client, cert)
    assert b["valid"] is False and not b["checked"][0]["ok"]


def test_fewer_than_quorum_votes(client, run_c):
    rid, _ = run_c
    cert = _cert(client, rid)
    cert["votes"] = cert["votes"][:2]
    b = _verify(client, cert)
    assert b["quorum_met"] is False and b["valid"] is False and all(c["ok"] for c in b["checked"])
    cert["votes"] = _cert(client, rid)["votes"][:3]
    assert _verify(client, cert)["quorum_met"] is True


def test_wrong_round_label_fails(client, run_c):
    rid, _ = run_c
    cert = _cert(client, rid, 0)
    cert["round"] = 1
    b = _verify(client, cert)
    assert b["valid"] is False and {c["reason"] for c in b["checked"]} == {"wrong_round"}


def test_malformed_hex_is_reported_not_crashed(client, run_c):
    rid, _ = run_c
    cert = _cert(client, rid)
    cert["votes"][0]["payload"] = "zz"
    b = _verify(client, cert)
    assert b["checked"][0] == {"node": 0, "ok": False, "reason": "malformed"} and b["valid"] is False


def test_unknown_round_and_run(client, run_c):
    rid, _ = run_c
    assert client.post("/api/certificates/verify", json={"run_id": rid, "round": 99}).status_code == 404
    assert client.post("/api/certificates/verify", json={"run_id": "nope", "round": 0}).status_code == 404
    assert client.post("/api/certificates/verify", json={}).status_code == 422


def test_verifier_registry_has_no_secrets(client, run_c):
    from pq import registry as rg
    from backend import run_queue
    rid, _ = run_c
    snap = run_queue.QUEUE.jobs[rid].states[0]["registry"]
    reg = rg.KeyRegistry.from_snapshot(snap)
    assert reg._sk == {}
    assert "sk" not in str(sorted(snap)) and "secret" not in str(sorted(snap))
