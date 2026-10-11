"""Forgery demonstration.  python -m pq.forgery --config configs/phase2.yaml

*** SIMULATION. No quantum computer is involved. ***
The adversary is simply GIVEN the victim client's Ed25519 secret key. That stands in for what a
quantum adversary running Shor's algorithm could derive from the victim's public key. The
adversary does NOT get the victim's ML-DSA key (a Shor-style attack does not break lattice
signatures; that assumption is the point of the experiment, not something proved here).

Part A: one round, one forged update (the victim's real delta scaled x50), checked by the real
aggregator path under each signature mode, in two forms: Ed25519 + junk PQ signature (matches the
verifier's required set) and Ed25519 only (downgrade attempt).
Part B: the same forgery injected every round of the FL loop with plain FedAvg.
"""
import argparse
import logging

import numpy as np

from attacks import poison
from fl import client, data, model
from fl import fixedpoint as fx
from fl.simulate import ROOT, load_cfg, run
from attacks import envelope_attacks
from pq import session as pqsession

BANNER = "SIMULATION: the adversary is handed the victim's Ed25519 secret key; no quantum computer is used."


def part_a(cfg, seed, victim, pq_alg):
    clients, _ = data.load(seed, cfg["clients"])
    w = model.init(seed)
    lr_fx = int(fx.to_fx(cfg["fl"]["lr"]))
    idx = client.sample_indices(seed, 0, victim, cfg["fl"]["K"], cfg["fl"]["batch"], len(clients[victim]))
    honest = client.local_train(w, clients[victim], idx, lr_fx)
    forged = poison.scaled(honest, cfg.get("attack", {}).get("scale", 50))
    rows = []
    for mode in ("classical", "pq", "hybrid"):
        s = pqsession.Session(mode, pq_alg, "Ed25519", cfg["clients"], cfg["aggregators"], seed, cfg["epoch_rounds"],
                              pqsession.merkle_roots(clients))
        s.begin_round(0, w)
        ok_h, r_h = s.verifier.verify_envelope(s.client_envelope(0, victim, honest), honest)   # control: honest update
        row = {"mode": mode, "honest update": f"{'accepted' if ok_h else 'REJECTED'} ({r_h})"}
        for name, stripped in (("forged: Ed25519 + junk PQ sig", False), ("forged: Ed25519 only (downgrade)", True)):
            s2 = pqsession.Session(mode, pq_alg, "Ed25519", cfg["clients"], cfg["aggregators"], seed, cfg["epoch_rounds"],
                                   pqsession.merkle_roots(clients))
            s2.begin_round(0, w)
            env, d = envelope_attacks.forge_with_classical_key(s2, victim, 0, forged, stripped=stripped)
            ok, reason = s2.verifier.verify_envelope(env, d)
            row[name] = f"{'ACCEPTED' if ok else 'rejected'} ({reason})"
        rows.append(row)
    return rows, float(np.sqrt(fx.norm_sq(forged)) / fx.ONE), float(np.sqrt(fx.norm_sq(honest)) / fx.ONE)


def part_b(cfg, seeds, pq_alg):
    rows = []
    for mode in ("none", "classical", "pq", "hybrid"):
        accs, drops = [], 0
        for sd in seeds:
            st = {}
            acc = run(cfg, "none", "fedavg", sd, None, stats=st, signatures=mode, sig_alg=pq_alg,
                      env_attack=None if mode == "none" else "forge_junk")
            accs.append(acc[-1])
            drops += sum(st.get("dropped", {}).values())
        rows.append((mode, float(np.mean(accs)), float(np.std(accs)), drops, len(seeds) * cfg["rounds"]))
    clean = [run(cfg, "none", "fedavg", sd, None, signatures="none")[-1] for sd in seeds]
    return rows, float(np.mean(clean)), float(np.std(clean))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/phase2.yaml")
    a = ap.parse_args()
    logging.disable(logging.WARNING)
    p2 = load_cfg(a.config)
    cfg, f = load_cfg(p2["base"]), p2["forgery"]
    pq_alg = p2["pq_alg"]
    rows_a, n_forged, n_honest = part_a(cfg, f["seed"], f["victim"], pq_alg)
    rows_b, clean_m, clean_s = part_b(cfg, p2["seeds"], pq_alg)
    md = [f"# Forgery demonstration\n\n**{BANNER}**\n",
          f"Victim: client {f['victim']}. Forged update = victim's honest round-0 update x{cfg['attack']['scale']} "
          f"(||Δ|| {n_honest:.3f} -> {n_forged:.3f}; norm bound B = {cfg['norm_bound_B']}). PQ scheme: {pq_alg}.\n",
          "## A. One round, real aggregator path (Verifier.verify_envelope)\n",
          "| mode | honest update (control) | forged: Ed25519 + junk PQ sig | forged: Ed25519 only (downgrade) |", "|---|---|---|---|"]
    for r in rows_a:
        md.append(f"| {r['mode']} | {r['honest update']} | {r['forged: Ed25519 + junk PQ sig']} | {r['forged: Ed25519 only (downgrade)']} |")
    md += ["", f"## B. Forgery injected every round into FL (FedAvg, no norm filter), seeds {p2['seeds']}\n",
           f"Reference, no forgery and no signatures: final accuracy {clean_m:.4f} ± {clean_s:.4f}. "
           "A diverged run (int64 range exceeded, D-012) is scored 0.0.\n",
           "| signatures | final accuracy (mean ± std) | forged updates dropped / injected |", "|---|---|---|"]
    for mode, m, s, drops, total in rows_b:
        md.append(f"| {mode} | {m:.4f} ± {s:.4f} | {drops} / {total if mode != 'none' else 0} |")
    md += ["", "Reading: under `classical` the forged update carries a valid Ed25519 signature, so the aggregator cannot tell it "
           "from the victim's and FedAvg is destroyed; under `pq` and `hybrid` the missing/invalid ML-DSA signature gets it dropped "
           "before aggregation. `none` has no check at all (the injection is not applied because there is no envelope to forge).",
           "", "Limits: the forged update here is scaled x50, which the Phase 1 norm filter would also catch; the demonstration "
           "isolates the signature layer by using plain FedAvg. Signatures prove who sent an update, not that it is good: "
           "a client signing its own poisoned update with its own valid key is accepted under every mode."]
    out = ROOT / f["out_md"]
    out.write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
