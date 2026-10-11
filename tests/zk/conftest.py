"""Fixtures for the Phase 3 ZK tests. No stubs: every receipt here is a real RISC Zero proof and every
verification calls the real `qs-zk` binary. Dev mode is never enabled.

Markers (registered here, nowhere else):
  real_proof  needs the one honest real proof (about 7 minutes, 2.4 GB); produced once per session by the
              `honest` fixture and cached in demo/results/zk/test_cache/ keyed by image id + input hash.
  prover_cli  calls `qs-zk prove` on a FALSE statement: the guest fails in the executor (exit 3), no proving
              work is done, but the call still takes the prove lock first (so it may wait for another prover).
  slow        takes more than a minute.
  dev_mode    reserved for clearly labelled RISC0_DEV_MODE tests (none exist; never use for numbers).
"""
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
import yaml

from fl import data, model
from fl import fixedpoint as fx
from fl import zk_reference as zr
from fl.merkle import MerkleTree
from pq import envelope as ev
from pq import session as pqsession
from pq import zkpolicy
from zk.bridge import cli

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "demo" / "results" / "zk" / "test_cache"


def pytest_configure(config):
    for m, d in [("real_proof", "needs the one honest real proof (cached); skipped if qs-zk is missing"),
                 ("prover_cli", "calls qs-zk prove on a false statement (exit 3 in the executor, no proving)"),
                 ("slow", "takes more than a minute"),
                 ("dev_mode", "labelled RISC0_DEV_MODE test (none; no number from it may be reported)")]:
        config.addinivalue_line("markers", f"{m}: {d}")


def _need_binary():
    if not cli.binary().exists():
        pytest.skip(f"qs-zk binary not found at {cli.binary()}: build zk/ (cargo build --release) to run this test")


def _load(path):
    p = ROOT / path
    cfg = yaml.safe_load(p.read_text())
    if "base" in cfg:
        base = _load(cfg.pop("base"))
        base.update(cfg)
        cfg = base
    return cfg


@dataclass
class World:
    cfg: dict
    seed: int
    K: int
    batch: int
    lr_fx: int
    B2: int
    clients: list
    trees: list
    w: np.ndarray

    def policy(self):
        return zkpolicy.ZkPolicy(cli.verify_receipt, [len(d) for d in self.clients], self.K, self.batch,
                                 self.seed, self.lr_fx, self.B2)

    def session(self):
        """Fresh hybrid Session (Ed25519 + ML-DSA-65) with the real ZkPolicy, positioned at round 0."""
        c = self.cfg
        s = pqsession.Session("hybrid", c.get("sig_alg", "ML-DSA-65"), c.get("classical_alg", "Ed25519"),
                              c["clients"], c["aggregators"], self.seed, c.get("epoch_rounds", 5),
                              [t.root for t in self.trees], zk=self.policy())
        s.begin_round(0, self.w)
        return s

    def blob(self, t, c, w=None):
        w = self.w if w is None else w
        return cli.client_blob(w, self.clients[c], t, c, self.seed, self.K, self.batch, self.lr_fx, self.B2,
                               ev.make_nonce(self.seed, t, c), self.trees[c])


@pytest.fixture(scope="session")
def world():
    cfg = _load("configs/phase3.yaml")
    seed = int(cfg["seeds"][0])
    clients, _ = data.load(seed, cfg["clients"])
    return World(cfg, seed, cfg["fl"]["K"], cfg["fl"]["batch"], int(fx.to_fx(cfg["fl"]["lr"])),
                 fx.bound_sq(cfg["norm_bound_B"]), clients, [MerkleTree(d.X, d.y) for d in clients],
                 model.init(seed).astype(np.int64))


@dataclass
class Honest:
    blob: bytes
    delta: np.ndarray
    receipt: bytes
    journal: bytes
    stats: dict
    cached: bool
    image_id: str


@pytest.fixture(scope="session")
def honest(world):
    """THE honest real proof (client 0, round 0). Proof 1 of 1 in this suite."""
    _need_binary()
    blob, delta = world.blob(0, 0)
    iid = cli.image_id()
    key = hashlib.sha256(iid.encode() + hashlib.sha256(blob).digest()).hexdigest()[:20]
    CACHE.mkdir(parents=True, exist_ok=True)
    rp, jp, sp = CACHE / f"{key}.receipt", CACHE / f"{key}.journal", CACHE / f"{key}.stats.json"
    cached = rp.exists() and jp.exists() and sp.exists()
    if cached:
        stats = json.loads(sp.read_text())
        print(f"\n[honest] reusing cached real proof {rp.name} (prove_s={stats.get('prove_s')})")
    else:
        t0 = time.time()
        stats = cli.prove_update(blob, rp, jp, po2=world.cfg["zk"]["po2"], kind=world.cfg["zk"]["receipt_kind"])
        sp.write_text(json.dumps(stats))
        print(f"\n[honest] REAL PROOF produced in {time.time() - t0:.0f}s wall: {stats}")
    return Honest(blob, delta, rp.read_bytes(), jp.read_bytes(), stats, cached, iid)


def run_verify(receipt_bytes, expected, tmp_path):
    """Direct `qs-zk verify` -> (exit code, stderr), to assert the documented exit codes."""
    (tmp_path / "r.bin").write_bytes(receipt_bytes)
    (tmp_path / "pub.bin").write_bytes(expected)
    r = cli._run(["verify", "--receipt", tmp_path / "r.bin", "--expect", tmp_path / "pub.bin"], timeout=300)
    return r.returncode, r.stderr.strip()
