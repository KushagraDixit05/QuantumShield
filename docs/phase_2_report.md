# Phase 2 Report — Post-quantum signatures on updates and votes

Scope: Phase 2 only. No ZK guest, no consensus. Nothing committed (the directory is not a git repository).

## Hardware / software
Intel i5-11260H @ 2.60 GHz (12 threads), 7.5 GiB RAM, Linux 7.0.0-34, Python 3.11.17, liboqs 0.16.0, liboqs-python 0.16.0.1, cryptography 50.0.2. Single process, sequential, CPU only. Benchmarks were run one at a time with nothing else running.

## What was built
| Path | Purpose |
|---|---|
| `pq/sig.py` | `keygen`/`sign`/`verify` for ML-DSA-44, ML-DSA-65, Falcon-512, SLH-DSA-128s (liboqs `SLH_DSA_PURE_SHA2_128S`) and Ed25519; `verify` never raises. `seed_rng` makes keys and signatures reproducible through liboqs's custom RNG hook (D-015) |
| `pq/envelope.py` | Update/vote payload layouts, domain tags `QSFL-env-v1` / `QSFL-vote-v1`, `commit` (C_i per `zk_statement.md`), `model_hash`, nonces, `Envelope` (+ wire encoding), `sign_update`, `sign_payload` |
| `pq/policy.py` | `Verifier` with modes `none|classical|pq|hybrid`; `verify_envelope` is the only way an update is admitted; `verify_vote` |
| `pq/registry.py` | Simulated PKI: per-client/aggregator keys, per-epoch rotation, revocation, JSON snapshot (public data only) |
| `pq/votes.py` | Vote message and signing (no consensus) |
| `pq/session.py` | FL-run glue: registry, verifier, Merkle roots (first use of `fl/merkle.py`), drop logging, vote signing/verifying |
| `pq/bench.py`, `pq/forgery.py` | Benchmark and forgery simulation |
| `attacks/envelope_attacks.py` | tamper-delta, stolen-classical-key forgery (junk-PQ and stripped variants) |
| `fl/simulate.py` (edited) | `signatures`/`sig_alg`/`env_attack`; unsigned deltas never reach `DEFENCES`; `none` is the unchanged path. `fl/aggregate.py` untouched |
| `experiments/run_phase2.py`, `configs/phase2.yaml`, `configs/mvp.yaml` (4 keys added), `Makefile` (`sigbench`, `forgery`, `phase2`) | One-command experiments |
| `tests/test_pq.py`, `test_registry.py`, `test_signed_fl.py` | 61 new tests |
| `docs/decisions.md` | D-014, D-015, D-016 |
| `demo/results/` | `sig_bench*.csv/.md`, `phase2_fl.csv/.md`, `forgery.md` |

Phase 1 settings (data, model, K, batch, lr, B = 1.5963, 10 rounds, 5 clients) are unchanged. Defaults added to `configs/mvp.yaml`: `signatures: none`, `sig_alg: ML-DSA-65`, `classical_alg: Ed25519`, `epoch_rounds: 5` (keys rotate at round 5, so every 10-round run crosses an epoch).

## Commands and real output
```
$ .venv/bin/python -m pytest -q
95 passed in 28.60s          # 34 Phase 1 + 61 new; a second run: 95 passed in 33.92s

$ .venv/bin/python -m pq.bench          # make sigbench; 4m08s wall (SLH-DSA signing 500 envelopes dominates)
$ make phase2                           # 62.6 s
$ make forgery
$ make baseline; diff <saved Phase 1 baseline.csv> demo/results/baseline.csv     -> BASELINE_IDENTICAL
$ make phase2 (again); diff                                                        -> PHASE2_FL_IDENTICAL
$ make forgery (again); diff                                                       -> FORGERY_IDENTICAL
```
Outputs are in the tables below and in `demo/results/`. Every experiment is seeded and runs from `configs/`; the repeat runs were byte-identical. Timings are not reproducible to the digit (benchmark uses the system RNG; see D-015).

## Benchmark (`demo/results/sig_bench.md`)
Medians in ms, p95 in brackets; 150-byte message; reps: keygen 50, sign 300 (SLH-DSA 20), verify 500.

| algorithm | pk (B) | sig (B) | keygen ms | sign ms | verify ms |
|---|---|---|---|---|---|
| Ed25519 | 32 | 64 | 0.032 (0.038) | 0.058 (0.063) | 0.088 (0.094) |
| ML-DSA-44 | 1312 | 2420 | 0.032 (0.049) | 0.056 (0.131) | 0.020 (0.020) |
| ML-DSA-65 | 1952 | 3309 | 0.038 (0.042) | 0.071 (0.171) | 0.027 (0.030) |
| Falcon-512 | 897 | 656 (max 752) | 4.851 (7.217) | 0.202 (0.209) | 0.037 (0.041) |
| SLH-DSA-128s | 32 | 7856 | 53.2 (60.0) | 450.4 (479.8) | 0.474 (0.568) |

Bytes added by the signature layer (real wire encoding; the update itself is 19,280 B):

| config | per update envelope | % of update | per vote | per round (5 updates + 4 votes) |
|---|---|---|---|---|
| Ed25519 | 94 | 0.5% | 91 | 834 |
| ML-DSA-44 | 2454 | 12.7% | 2451 | 22074 |
| ML-DSA-65 | 3343 | 17.3% | 3340 | 30075 |
| Falcon-512 | 688 | 3.6% | 689 | 6196 |
| SLH-DSA-128s | 7896 | 41.0% | 7893 | 71052 |
| hybrid Ed25519+ML-DSA-65 | 3436 | 17.8% | 3430 | 30900 |

Verification throughput of the full `verify_envelope` path (key checks, signature(s), commitment hash over the 19 KB delta, nonce), sequential, median of 3 runs, envelopes/s:

| config | 50 clients | 100 clients | 500 clients |
|---|---|---|---|
| Ed25519 | 8196 | 7944 | 8149 |
| ML-DSA-44 | 18882 | 21181 | 20711 |
| ML-DSA-65 | 17671 | 17792 | 17270 |
| Falcon-512 | 17408 | 17111 | 17229 |
| SLH-DSA-128s | 2348 | 2264 | 2330 |
| hybrid Ed25519+ML-DSA-65 | 7106 | 7101 | 7022 |

Caveats: Ed25519 verify looks slower than ML-DSA here mostly because the `cryptography` binding parses the public key on every call and is not batched; it is a Python-wrapper number, not a statement about the algorithms. An earlier partial run of the same benchmark gave ML-DSA-65 verify throughput of ~21–22k/s versus 17k/s in the final run, so run-to-run variation is about 20%. Single-thread numbers; nothing was parallelised.

## FL results (`demo/results/phase2_fl.md`)
Final-round accuracy, seeds 0–4, mean ± std, ML-DSA-65 for pq/hybrid:

| scenario (defence) | none | classical | pq | hybrid |
|---|---|---|---|---|
| benign (fedavg) | 0.9421 ± 0.0145 | 0.9421 ± 0.0145 | 0.9421 ± 0.0145 | 0.9421 ± 0.0145 |
| scaled ×50, own valid key (norm_filter) | 0.9376 ± 0.0165 | same | same | same |
| stale delta re-signed by its owner (fedavg) | 0.9265 ± 0.0189 | same | same | same |
| old envelope resent verbatim (fedavg) | n/a | 0.9370 ± 0.0158; dropped wrong_round 40, stale_key 5 | same | same |
| delta altered after signing (fedavg) | n/a | 0.9376 ± 0.0165; dropped commitment_mismatch 50 | same | same |

Benign accuracy matches Phase 1 (0.9421 ± 0.0145) exactly, and the per-round curves are identical across modes for every seed (signatures never touch a delta). FL loop also run once per PQ algorithm, seed 0: ML-DSA-44, ML-DSA-65, Falcon-512, SLH-DSA-128s all end at 0.9526, identical to `none` (SLH-DSA took 37.6 s for the run because of its signing cost, the others ~0.3 s). All 4 aggregators' votes were signed and verified every round (checked in the tests: 40/40 per run, 0 rejected).

Two results the signatures do **not** change: a malicious client signing its own scaled update with its own valid key is accepted by every mode (the norm filter catches it, as in Phase 1), and the Phase 1 `replay` attack (a stale delta re-signed under a fresh round and nonce) is accepted too. Only a verbatim resend of an old envelope is dropped. See D-016 and open issue 2.

## Tests
`95 passed` (34 Phase 1 + 61 new). New tests, by file:
- `tests/test_pq.py`: every algorithm signs/verifies; tampered signature, truncated/empty signature, wrong public key, wrong key all fail without raising; seeded keys and signatures reproducible per algorithm; valid update accepted in classical/pq/hybrid for all four PQ algorithms; wire round trip and malformed input; tampered payload (nonce byte → `bad_signature`); tampered delta (`commitment_mismatch`, and the failed attempt does not burn the nonce); wrong round (past and future); wrong model hash; replayed nonce (same envelope, reused nonce in a later round, second submission in a round); old envelope resent next round; wrong key (attacker's own PKI, and another client's genuine key); revoked key; key retired by epoch rotation; downgrade hybrid→classical, hybrid→PQ-only, hybrid→unsigned, and classical/pq verifiers refusing the wrong scheme set; relabelled algorithm; votes: domain separation both ways, re-tagged payload, client key signing a vote, replayed and wrong-round votes.
- `tests/test_registry.py`: snapshot round trip with no secret keys on disk, revocation/stale/unknown status, deterministic keys per seed and epoch, key-id parsing.
- `tests/test_signed_fl.py`: convergence identical to Phase 1 under all four modes; each PQ algorithm in the loop; drops logged with reason and excluded from aggregation; replayed envelope dropped; stale-delta and own-key scaled attacks pass signatures; forgery with a stolen Ed25519 key (both variants) accepted under classical and dropped under pq and hybrid; `env_attack` refused under `none`; a source-level check that `deltas.append` happens once, after `sess.admit`.

## Forgery demonstration (`demo/results/forgery.md`)
**Simulation.** The adversary is handed client 0's Ed25519 secret key as a stand-in for what Shor's algorithm would recover from the public key. No quantum computer is involved, and the assumption that ML-DSA keys are not recoverable is assumed, not shown by this experiment. The forged update is the victim's honest round-0 update ×50 (‖Δ‖ 0.952 → 47.608, B = 1.5963).

| mode | honest update (control) | forged: Ed25519 + junk PQ sig | forged: Ed25519 only (downgrade) |
|---|---|---|---|
| classical | accepted | **ACCEPTED** | **ACCEPTED** |
| pq | accepted | rejected (bad_signature) | rejected (scheme_downgrade) |
| hybrid | accepted | rejected (bad_signature) | rejected (scheme_downgrade) |

Forgery injected every round into FL with FedAvg, 5 seeds: `classical` 0.0000 ± 0.0000 (diverged, 0/50 dropped); `pq` and `hybrid` 0.9409 ± 0.0161 (50/50 dropped); reference without forgery 0.9421 ± 0.0145. The ×50 forgery would also be caught by the norm filter; plain FedAvg is used to isolate the signature layer. The 0.9409 vs 0.9421 gap is because the victim's own honest update is dropped too, leaving 4 clients.

## Deviations and open issues
Deviations (details in `docs/decisions.md` D-014..D-016):
1. Envelope fields follow the brief (H(W_t), R_i) instead of the plan's `proof_hash`; Falcon, SLH-DSA, hybrid and rotation were built though the plan listed them as deferred; baseline is Ed25519 not ECDSA-P256.
2. Replay: the plan implied signed envelopes stop the replay attack. They stop only verbatim resends. A malicious client re-signing a stale delta passes; that needs the ZK proof's binding to H(W_t) (Phase 3). Reported rather than hidden.
3. `signatures: none` is an explicit unsigned path (needed so Phase 1 stays reproducible and "every setting works"). The plan's "no unsigned path" holds for all other modes.
4. Seeded RNG uses a liboqs custom-RNG hook because the seeding call is not exported by this build. It is for experiments only.
5. Verbatim resend across the epoch boundary is reported as `stale_key` rather than `wrong_round` (key check runs before the round check).

Open issues:
1. `R_i` is signed but not checked against anything; no one verifies it is the client's real data until the proof exists.
2. Signatures authenticate senders, not data or updates. In-bound poisoning, label flipping and stale re-signed deltas pass.
3. Δ is still sent in the clear; the signature binds it through C_i only.
4. The PKI is simulated: no enrolment, no certificate chain, secret keys live in the same process, revocation is a local set with no distribution.
5. Hybrid verification costs both checks (≈7.0k envelopes/s vs 17k/s for ML-DSA-65 alone, in this Python wrapper); the bandwidth cost (3.4 KB per update, 17.8% of the update) is dominated by the PQ signature.
6. Benchmarks are single-threaded Python-wrapper numbers on one machine, with ~20% run-to-run variation ; side-channel and constant-time properties of the liboqs builds were not examined.
7. Votes are signed and verified only; no quorum or leader logic exists yet.
