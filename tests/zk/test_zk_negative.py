"""Statement-false cases against the real guest, via real `qs-zk prove` (no proving work: the guest fails in
the executor, exit 3), and aggregator-side rejections that need no receipt. No stubs."""
import numpy as np
import pytest

from attacks import poison
from fl import zk_reference as zr
from pq import envelope as ev
from zk.bridge import cli

from conftest import _need_binary

pytestmark = pytest.mark.prover_cli


def rebuild(blob, recommit=False, **chg):
    p = zr.parse_input(blob)
    p.pop("n_open")
    p.update(chg)
    if recommit:
        p["C"] = zr.commit(p["delta"], p["nonce"])
    return zr.build_input(**p)


def prove_fails(blob, tmp_path):
    """-> (exit code, stderr) of a real `qs-zk prove` on `blob`."""
    _need_binary()
    with pytest.raises(cli.ZkError) as e:
        cli.prove_update(blob, tmp_path / "r.bin", tmp_path / "j.bin")
    assert not (tmp_path / "r.bin").exists(), "a receipt exists for a false statement"
    return e.value.code, e.value.stderr


@pytest.fixture(scope="module")
def base(world):
    blob, delta = world.blob(0, 0)
    assert zr.evaluate(blob)[0], "the honest blob must satisfy the reference"
    return blob, [int(v) for v in delta]


def case(name, blob, tmp_path, any_of):
    ref_ok, _, ref_reason = zr.evaluate(blob)
    code, err = prove_fails(blob, tmp_path)
    print(f"[{name}] reference={ref_reason}; qs-zk prove exit={code}: {err}")
    assert not ref_ok and code == 3 and "guest-failed" in err
    assert any(s in err for s in any_of), f"{name}: guest message {err!r} names none of {any_of}"


def test_scaled_update_x50_norm_bound(world, base, tmp_path):
    blob, delta = base
    d50 = [int(v) for v in poison.scaled(np.array(delta), 50)]
    case("scaled_x50", rebuild(blob, True, delta=d50), tmp_path, ["norm bound"])


def test_scaled_update_rejected_by_aggregator_without_receipt(world):
    """The attacker (client 4) has no receipt. v2 envelope without receipt -> missing_receipt; v1 envelope
    (no proof_hash) -> missing_proof_hash. Both are the ZkPolicy layer, after signatures and commitment pass."""
    sess = world.session()
    c, atk = 0, 4
    from fl import client as flc
    idx = flc.sample_indices(world.seed, 0, atk, world.K, world.batch, len(world.clients[atk]))
    d = poison.scaled(flc.local_train(world.w, world.clients[atk], idx, world.lr_fx), 50)
    env2 = sess.client_envelope(0, atk, d, receipt=b"attacker-claimed-proof")        # v2, receipt not delivered
    assert sess.admit(0, atk, env2, d, None) is False
    assert sess.drop_log[-1] == (0, atk, "bad_proof:missing_receipt"), sess.drop_log
    env1 = sess.client_envelope(0, atk, d)                                           # v1
    assert sess.admit(0, atk, env1, d, None) is False
    assert sess.drop_log[-1] == (0, atk, "bad_proof:missing_proof_hash"), sess.drop_log
    print("[aggregator] scaled x50 dropped:", sess.drop_log)


def test_wrong_commitment(base, tmp_path):
    blob, _ = base
    case("C_random", rebuild(blob, C=bytes(range(32))), tmp_path, ["commitment"])
    case("nonce_changed", rebuild(blob, nonce=bytes(32)), tmp_path, ["commitment"])


def test_wrong_model_hash(base, tmp_path):
    blob, _ = base
    case("H_w_wrong", rebuild(blob, h_w=bytes(32)), tmp_path, ["model hash"])


def test_fabricated_update_delta_mismatch(base, tmp_path):
    blob, delta = base
    d1 = list(delta); d1[7] += 1
    case("delta_plus_one", rebuild(blob, True, delta=d1), tmp_path, ["delta mismatch"])
    rng = np.random.default_rng(7)
    drand = [int(v) for v in rng.integers(-3, 4, len(delta))]
    assert sum(v * v for v in drand) <= world_b2(blob)
    case("small_random_delta", rebuild(blob, True, delta=drand), tmp_path, ["delta mismatch"])


def world_b2(blob):
    return zr.parse_input(blob)["B2"]


def _mut_opening(blob, fn):
    p = zr.parse_input(blob)
    p.pop("n_open")
    ops = [list(o) for o in p["openings"]]
    fn(ops)
    p["openings"] = [tuple(o) for o in ops]
    return zr.build_input(**p)


def test_wrong_merkle_path_flipped_sibling(base, tmp_path):
    def f(ops):
        s = bytearray(ops[0][3][0]); s[0] ^= 1
        ops[0][3] = [bytes(s)] + list(ops[0][3][1:])
    case("flipped_sibling_bit", _mut_opening(base[0], f), tmp_path, ["merkle"])


def test_wrong_merkle_path_too_short(base, tmp_path):
    """Dropping one sibling shifts the byte layout (opening size is fixed by depth(n_c)), so the guest
    rejects at the first structurally impossible point; all of these are rejections of the same statement."""
    def f(ops):
        ops[0][3] = list(ops[0][3][:-1])
    case("path_too_short", _mut_opening(base[0], f), tmp_path,
         ["merkle", "opening order", "opening count", "short input", "trailing bytes", "label"])


def test_wrong_merkle_leaf_data(base, tmp_path):
    def f(ops):
        x = list(ops[0][1]); x[0] += 1
        ops[0][1] = x
    case("leaf_x_changed", _mut_opening(base[0], f), tmp_path, ["merkle"])


def test_wrong_merkle_root(base, tmp_path):
    blob, _ = base
    R = bytearray(zr.parse_input(blob)["R"]); R[0] ^= 1
    case("root_R_wrong", rebuild(blob, R=bytes(R)), tmp_path, ["merkle"])


def test_v1_envelope_under_zkpolicy_needs_no_binary(world, base):
    """Cheap sanity: with a v1 envelope the policy answers before any binary is involved."""
    sess = world.session()
    d = base[1]
    env = sess.client_envelope(0, 0, np.array(d, dtype=np.int64))
    assert sess.admit(0, 0, env, np.array(d, dtype=np.int64), b"x") is False
    assert sess.drop_log[-1][2] == "bad_proof:missing_proof_hash"
