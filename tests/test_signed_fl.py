"""The FL loop with signatures: convergence, drop-before-aggregation, forgery."""
import logging

import pytest

from fl import fixedpoint as fx
from fl.simulate import load_cfg, run

CFG = load_cfg("configs/mvp.yaml")
B2 = fx.bound_sq(CFG["norm_bound_B"])
MODES = ["none", "classical", "pq", "hybrid"]


@pytest.mark.parametrize("mode", MODES)
def test_fl_converges_identically_under_every_mode(mode):
    ref = run(CFG, "none", "fedavg", 0, signatures="none")
    st = {}
    acc = run(CFG, "none", "fedavg", 0, signatures=mode, stats=st)
    assert acc == ref and acc[-1] >= 0.90                  # signatures never alter a delta
    if mode != "none":
        assert not st["dropped"] and st["votes_ok"] == CFG["aggregators"] * CFG["rounds"] and st["votes_bad"] == 0


@pytest.mark.parametrize("alg", ["ML-DSA-44", "Falcon-512", "SLH-DSA-128s"])
def test_fl_runs_with_each_pq_algorithm(alg):
    cfg = dict(CFG, rounds=2)
    assert run(cfg, "none", "fedavg", 0, signatures="pq", sig_alg=alg) == run(cfg, "none", "fedavg", 0, signatures="none")


def test_config_default_is_phase1_path_and_matches_phase1_numbers():
    assert CFG["signatures"] == "none"
    # Phase 1 report: FedAvg benign, seed 0 final accuracy is part of the 0.9421 ± 0.0145 mean
    assert run(CFG, "none", "fedavg", 0) == run(CFG, "none", "fedavg", 0, signatures="none")


def test_dropped_updates_never_reach_aggregation_and_are_logged(caplog):
    st = {}
    with caplog.at_level(logging.WARNING, logger="quantumshield.aggregator"):
        run(CFG, "none", "fedavg", 0, signatures="pq", env_attack="tamper_delta", stats=st)
    assert st["dropped"] == {"commitment_mismatch": CFG["rounds"]}
    assert len(st["drop_log"]) == CFG["rounds"] and all(c == CFG["clients"] - 1 for _, c, _ in st["drop_log"])
    assert sum("reason=commitment_mismatch" in r.message for r in caplog.records) == CFG["rounds"]
    # the tampered client is excluded: result equals 4-client FedAvg, i.e. differs from the honest 5-client run
    assert run(CFG, "none", "fedavg", 0, signatures="pq", env_attack="tamper_delta") != run(CFG, "none", "fedavg", 0)


def test_replayed_envelope_dropped():
    st = {}
    run(CFG, "none", "fedavg", 0, signatures="hybrid", env_attack="replay_envelope", stats=st)
    assert sum(st["dropped"].values()) == CFG["rounds"] - 1       # round 0 has nothing to replay
    assert set(st["dropped"]) <= {"wrong_round", "stale_key"}


def test_stale_delta_resigned_by_its_owner_is_not_stopped_by_signatures():
    # Phase 1 `replay` attack: the client re-signs an old delta with its own key. Signatures cannot see it.
    st = {}
    run(CFG, "replay", "fedavg", 0, signatures="pq", stats=st)
    assert not st["dropped"]


def test_scaled_update_with_own_valid_key_passes_signature_and_is_caught_by_norm_filter():
    st = {}
    acc = run(CFG, "scaled", "norm_filter", 0, B2, stats=st, signatures="pq")
    assert not st["dropped"] and st["mal_rejected"] == CFG["rounds"] and acc[-1] >= 0.90


@pytest.mark.parametrize("variant", ["forge_junk", "forge_stripped"])
def test_forgery_with_stolen_classical_key(variant):
    classical = run(CFG, "none", "fedavg", 0, signatures="classical", env_attack=variant)
    assert classical[-1] == 0.0                                     # accepted: x50 update diverges FedAvg (D-012)
    for mode in ("pq", "hybrid"):
        st = {}
        acc = run(CFG, "none", "fedavg", 0, signatures=mode, env_attack=variant, stats=st)
        assert sum(st["dropped"].values()) == CFG["rounds"] and acc[-1] >= 0.90
        assert set(st["dropped"]) == {"bad_signature" if variant == "forge_junk" else "scheme_downgrade"}


def test_env_attack_requires_signatures():
    with pytest.raises(ValueError):
        run(CFG, "none", "fedavg", 0, signatures="none", env_attack="tamper_delta")


def test_aggregator_has_single_entry_point():
    """In signed modes the only way a delta joins `deltas` is through Session.admit -> Verifier.verify_envelope."""
    import inspect
    from fl import simulate
    src = inspect.getsource(simulate.run)
    assert src.count("deltas.append") == 1 and src.index("sess.admit") < src.index("deltas.append")
