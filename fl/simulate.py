"""Federated simulation in fixed point.  python -m fl.simulate --config configs/mvp.yaml --attack scaled --defence fedavg --seed 0"""
import argparse
import csv
import logging
from pathlib import Path

import numpy as np
import yaml

from attacks import envelope_attacks, poison
from pq import session as pqsession
from . import aggregate, client, data, model
from . import fixedpoint as fx

ROOT = Path(__file__).resolve().parent.parent
ATTACKS = ["none", "scaled", "sign_flip", "label_flip", "replay"]
# attacks on the signed envelope (need signatures != none): see attacks/envelope_attacks.py
ENV_ATTACKS = ["replay_envelope", "tamper_delta", "forge_junk", "forge_stripped"]


def load_cfg(path):
    p = Path(path)
    return yaml.safe_load((p if p.is_absolute() else ROOT / p).read_text())


def _submit(attack, atk, d, history):
    """The malicious client's submission for this round."""
    if attack == "scaled":
        d = poison.scaled(d, atk.get("scale", 50))
    elif attack == "sign_flip":
        d = poison.sign_flip(d, atk.get("flip_scale", 1))
    elif attack == "replay" and history:
        d = poison.replay(history)  # stale previous submission
    # label_flip: the client's data is already poisoned; d is a normal training output
    history.append(d)
    return d


def run(cfg, attack="none", defence="fedavg", seed=0, B2=None, return_norms=False, stats=None,
        signatures=None, sig_alg=None, env_attack=None):
    """Returns per-round test accuracy (index 0 = before training) [and benign update norms^2].

    signatures: none | classical | pq | hybrid (default cfg["signatures"]). With anything but
    "none", every submission is a signed envelope and only updates accepted by
    pq.policy.Verifier.verify_envelope reach the aggregation rule; drops are logged with a reason
    (stats["dropped"], stats["drop_log"]). "none" is the unchanged Phase 1 path.
    env_attack: optional attack on the envelope layer (ENV_ATTACKS), see attacks/envelope_attacks.py.

    If the global model leaves the int64 fixed-point range the run is marked diverged:
    accuracy is recorded as 0.0 from that round on and stats["diverged_round"] is set.
    """
    fl = cfg["fl"]
    n_clients, mal = cfg["clients"], cfg["malicious_clients"]
    n_benign = n_clients - mal
    clients, test = data.load(seed, n_clients)
    atk = cfg.get("attack", {})
    if attack == "label_flip":
        for c in range(n_benign, n_clients):
            clients[c] = poison.label_flip(clients[c], atk.get("label_shift", 1))
    w = model.init(seed)
    lr_fx = int(fx.to_fx(fl["lr"]))
    acc, norms, history = [model.accuracy(w, test)], [], []
    mode = signatures or cfg.get("signatures", "none")
    if env_attack and mode == "none":
        raise ValueError("env_attack needs signatures != none")
    sess = None
    if mode != "none":
        sess = pqsession.Session(mode, sig_alg or cfg.get("sig_alg", "ML-DSA-65"), cfg.get("classical_alg", "Ed25519"),
                                 n_clients, cfg["aggregators"], seed, cfg.get("epoch_rounds", 5),
                                 pqsession.merkle_roots(clients))
        prev_env = {}
    for t in range(cfg["rounds"]):
        try:
            deltas, ids = [], []
            if sess:
                sess.begin_round(t, w)
            for c in range(n_clients):
                idx = client.sample_indices(seed, t, c, fl["K"], fl["batch"], len(clients[c]))
                d = client.local_train(w, clients[c], idx, lr_fx)
                if c >= n_benign:
                    d = _submit(attack, atk, d, history)
                elif return_norms:
                    norms.append(fx.norm_sq(d))
                if sess:
                    env = sess.client_envelope(t, c, d)
                    honest = (env, d)
                    if env_attack == "replay_envelope" and c == n_clients - 1 and c in prev_env:
                        env, d = prev_env[c]               # resend last round's envelope verbatim
                    elif env_attack == "tamper_delta" and c == n_clients - 1:
                        env, d = envelope_attacks.tamper_delta(env, d)
                    elif env_attack in ("forge_junk", "forge_stripped") and c == 0:
                        env, d = envelope_attacks.forge_with_classical_key(
                            sess, 0, t, poison.scaled(d, atk.get("scale", 50)), stripped=env_attack == "forge_stripped")
                    prev_env[c] = honest
                    if not sess.admit(t, c, env, d):
                        continue
                deltas.append(d)
                ids.append(c)
            if stats is not None and B2 is not None and deltas:  # what the plain norm check would reject
                ok = aggregate.accepted_by_norm(deltas, B2)
                nb = sum(i < n_benign for i in ids)
                stats["benign_rejected"] = stats.get("benign_rejected", 0) + sum(not o for o, i in zip(ok, ids) if i < n_benign)
                stats["mal_rejected"] = stats.get("mal_rejected", 0) + sum(not o for o, i in zip(ok, ids) if i >= n_benign)
                stats["benign_total"] = stats.get("benign_total", 0) + nb
                stats["mal_total"] = stats.get("mal_total", 0) + len(ids) - nb
            if deltas:
                w = fx.check(w + aggregate.DEFENCES[defence](deltas, B2))
            if sess:
                sess.cast_votes(t, w, ids)
            acc.append(model.accuracy(w, test))
        except fx.FixedPointOverflow:
            if stats is not None:
                stats["diverged_round"] = t
            acc += [0.0] * (cfg["rounds"] + 1 - len(acc))
            break
    if sess and stats is not None:
        stats.update(dropped=dict(sess.dropped), drop_log=sess.drop_log, wire_bytes=sess.wire_bytes,
                     votes_ok=sess.votes_ok, votes_bad=sess.votes_bad)
    return (acc, norms) if return_norms else acc


def write_csv(path, acc, meta):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["round", "accuracy", *meta.keys()])
        for r, a in enumerate(acc):
            wr.writerow([r, f"{a:.6f}", *meta.values()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/mvp.yaml")
    ap.add_argument("--attack", default="none", choices=ATTACKS)
    ap.add_argument("--defence", default="fedavg", choices=list(aggregate.DEFENCES))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--signatures", default=None, choices=["none", "classical", "pq", "hybrid"])
    ap.add_argument("--sig-alg", default=None)
    ap.add_argument("--env-attack", default=None, choices=ENV_ATTACKS)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")
    cfg = load_cfg(a.config)
    seed = cfg["seed"] if a.seed is None else a.seed
    B = cfg.get("norm_bound_B")
    B2 = fx.bound_sq(B) if B else None
    if a.defence in ("norm_filter", "clip") and B2 is None:
        raise SystemExit("norm_bound_B not set; run experiments.run_baseline --calibrate first")
    st = {}
    acc = run(cfg, a.attack, a.defence, seed, B2, stats=st, signatures=a.signatures, sig_alg=a.sig_alg, env_attack=a.env_attack)
    out = a.out or f"demo/results/sim_{a.attack}_{a.defence}_s{seed}.csv"
    write_csv(ROOT / out, acc, {"attack": a.attack, "defence": a.defence, "seed": seed})
    extra = f" dropped={st['dropped']}" if st.get("dropped") else ""
    print(f"attack={a.attack} defence={a.defence} seed={seed} final_acc={acc[-1]:.4f}{extra} -> {out}")


if __name__ == "__main__":
    main()
