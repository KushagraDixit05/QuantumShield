"""Python bridge to the `qs-zk` host binary (docs/zk_interface.md section 9).

Binary: zk/target/release/qs-zk, override with env QS_ZK_BIN. Exit codes: 0 ok, 2 bad args/input,
3 guest failed, 4 receipt invalid, 5 journal mismatch, 6 lock or dev-mode refusal.
`verify_receipt(receipt_bytes, expected_public) -> (ok, reason)` is the callable pq.zkpolicy.ZkPolicy
expects. Nothing here proves or verifies anything itself; it only drives the binary.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BIN = ROOT / "zk" / "target" / "release" / "qs-zk"
REASONS = {2: "bad_input", 3: "guest_failed", 4: "receipt_invalid", 5: "journal_mismatch", 6: "refused"}


class ZkError(RuntimeError):
    def __init__(self, reason, code=None, stderr=""):
        super().__init__(f"{reason} (exit {code}): {stderr.strip()[:500]}")
        self.reason, self.code, self.stderr = reason, code, stderr


def binary():
    return Path(os.environ.get("QS_ZK_BIN") or DEFAULT_BIN)


def _run(args, timeout=None):
    b = binary()
    if not b.exists():
        raise ZkError("binary_missing", None, f"{b} not found; build zk/host or set QS_ZK_BIN")
    try:
        return subprocess.run([str(b), *map(str, args)], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise ZkError("timeout", None, str(e))


def _reason(code):
    return REASONS.get(code, f"error_{code}")


def image_id():
    r = _run(["image-id"], timeout=60)
    if r.returncode:
        raise ZkError(_reason(r.returncode), r.returncode, r.stderr)
    return r.stdout.strip()


def execute(blob, timeout=600):
    """Run the guest in the executor only (no proof). -> (ok, journal | None, stats dict).
    ok is False only for exit 3 (relation false); other failures raise ZkError."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "in.bin").write_bytes(blob)
        r = _run(["execute", "--input", d / "in.bin", "--journal", d / "j.bin", "--stats", d / "s.json"], timeout)
        if r.returncode == 3:
            return False, None, {"stderr": r.stderr.strip()}
        if r.returncode:
            raise ZkError(_reason(r.returncode), r.returncode, r.stderr)
        stats = json.loads((d / "s.json").read_text()) if (d / "s.json").exists() else {}
        return True, (d / "j.bin").read_bytes(), stats


def prove_update(blob, receipt_path, journal_path, po2=18, kind="composite", timeout=None):
    """Real proof (takes the prove lock inside the binary). Returns the stats dict.
    Raises ZkError('guest_failed') when the relation is false."""
    receipt_path, journal_path = Path(receipt_path), Path(journal_path)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "in.bin").write_bytes(blob)
        r = _run(["prove", "--input", d / "in.bin", "--receipt", receipt_path, "--journal", journal_path,
                  "--po2", po2, "--kind", kind, "--stats", d / "s.json"], timeout)
        if r.returncode:
            raise ZkError(_reason(r.returncode), r.returncode, r.stderr)
        return json.loads((d / "s.json").read_text())


def verify_receipt(receipt_bytes, expected_public):
    """-> (ok, reason) with reason in ok | guest_failed | receipt_invalid | journal_mismatch | ..."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "r.bin").write_bytes(receipt_bytes)
        (d / "pub.bin").write_bytes(expected_public)
        try:
            r = _run(["verify", "--receipt", d / "r.bin", "--expect", d / "pub.bin"], timeout=300)
        except ZkError as e:
            return False, e.reason
    return (True, "ok") if r.returncode == 0 else (False, _reason(r.returncode))


def client_blob(global_model, ds, rnd, client_id, seed, K, batch, lr_fx, B2, nonce, tree, relation=1):
    """Input blob from the real FL objects. The honest delta is fl.client.local_train's, i.e. the same
    one the Phase 1/2 pipeline commits to. `tree` is the fl.merkle.MerkleTree over ds. -> (blob, delta)."""
    import numpy as np

    from fl import client as flc
    from fl import zk_reference as zr
    w = np.asarray(global_model, dtype=np.int64)
    idx = flc.sample_indices(seed, rnd, client_id, K, batch, len(ds))
    delta = flc.local_train(w, ds, idx, lr_fx)
    d = [int(v) for v in delta]
    paths = {i: tree.path(i) for i in set(idx.ravel().tolist())}
    order = zr.unique_in_order(idx.tolist())
    openings = [(i, [int(v) for v in ds.X[i]], int(ds.y[i]), paths[i]) for i in order]
    kk, bb = (K, batch) if relation == 1 else (0, 0)
    blob = zr.build_input(relation=relation, t=rnd, c=client_id, n_c=len(ds), K=kk, batch=bb, seed=seed,
                          lr_fx=int(lr_fx), B2=int(B2), h_w=zr.model_hash(w), C=zr.commit(d, nonce),
                          R=tree.root, nonce=nonce, w_t=[int(v) for v in w], delta=d,
                          openings=openings if relation == 1 else ())
    return blob, delta


def client_prove(global_model, ds, rnd, client_id, seed, K, batch, lr_fx, B2, nonce, tree,
                 receipt_path, journal_path, po2=18, kind="composite", relation=1):
    """Build the blob and prove it. -> dict(stats=..., delta=..., commitment=..., root=..., blob=...)."""
    blob, delta = client_blob(global_model, ds, rnd, client_id, seed, K, batch, lr_fx, B2, nonce, tree, relation)
    stats = prove_update(blob, receipt_path, journal_path, po2=po2, kind=kind)
    return dict(stats=stats, delta=delta, commitment=blob[82:114], root=tree.root, blob=blob)
