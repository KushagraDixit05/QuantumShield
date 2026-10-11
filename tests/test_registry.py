import json

from pq import registry as rg


def test_snapshot_roundtrip_public_only(tmp_path):
    reg = rg.KeyRegistry(3, 2, ["Ed25519", "ML-DSA-65"], seed=3, epoch_rounds=2)
    reg.rotate()
    kid = reg.key_id("client", 1, "ML-DSA-65")
    reg.revoke(kid)
    f = tmp_path / "reg.json"
    reg.save(f)
    text = f.read_text()
    for sk in reg._sk.values():
        assert sk.hex() not in text                      # no secret key on disk
    back = rg.KeyRegistry.load(f)
    assert back.pks == reg.pks and back.revoked == reg.revoked and back.epoch == reg.epoch == 1
    assert back.status(kid) == "revoked"
    assert back.status(reg.key_id("client", 0, "ML-DSA-65")) == "ok"
    assert back.status(rg.make_key_id("client", 0, 0, "ML-DSA-65")) == "stale"
    assert back.status("client:99:0:ML-DSA-65") == "unknown"
    assert back._sk == {}
    json.loads(text)


def test_deterministic_keys_per_seed_and_epoch():
    a = rg.KeyRegistry(2, 1, ["Ed25519", "Falcon-512"], seed=5)
    b = rg.KeyRegistry(2, 1, ["Ed25519", "Falcon-512"], seed=5)
    c = rg.KeyRegistry(2, 1, ["Ed25519", "Falcon-512"], seed=6)
    assert a.pks == b.pks and a.pks != c.pks
    a.rotate()
    assert a.pks[rg.make_key_id("client", 0, 1, "Ed25519")] != a.pks[rg.make_key_id("client", 0, 0, "Ed25519")]


def test_parse_key_id():
    assert rg.parse_key_id("client:3:0:ML-DSA-65") == ("client", 3, 0, "ML-DSA-65")
    assert rg.parse_key_id("nope") is None and rg.parse_key_id("evil:1:0:ML-DSA-65") is None
    assert rg.parse_key_id("client:1:0:RSA") is None
