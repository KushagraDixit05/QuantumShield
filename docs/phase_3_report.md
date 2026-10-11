# Phase 3 Report — Zero-knowledge update verification (RISC Zero)

Scope: Phase 3 only. Phase 4 (consensus) not started. Nothing is committed; everything is in the working tree (the directory is not a git repository).

## Result in one paragraph
A client proves, with a real RISC Zero composite receipt, that its integer update Δ opens its commitment, satisfies ‖Δ‖² ≤ B², and equals the result of **K = 4 fixed-point SGD steps with batch 8** from the global model on samples that are Merkle-opened to the committed root R. The aggregator verifies the receipt before aggregation and binds it to the PQ-signed envelope (envelope v2, `proof_hash`). Every honest update verified; every negative case was rejected; the Python reference and the guest agree on all 86 test vectors. **K and batch are smaller than Phase 1 (K = 20, batch 32)** because K = 20, batch 32 would take hours per proof on this machine (D-017, D-019).

## Hardware / software
Intel i5-11260H @ 2.60 GHz (12 threads), 7.5 GiB RAM (browser and desktop apps were open, about 3–3.5 GiB available), Linux 7.0.0-34, CPU proving only, risc0-zkvm 3.0.6 (rust 1.97 risc0 toolchain), Python 3.11.17. Release builds. `RISC0_DEV_MODE` was never set; every number below is from a real proof.

## What was built
| Path | Purpose | Built by |
|---|---|---|
| `docs/zk_interface.md` (v1.4) | Shared contract: input/journal layout, fixed-point and guard rules, Merkle, sampling, CLI, exit codes, locks | lead |
| `docs/zk_cost.md`, `docs/decisions.md` (D-017..D-019) | Cost measurements, K/batch decision, envelope v2 | lead |
| `zk/probe/` | Throwaway cost probe (first guest, host, input builder) | lead |
| `zk/Cargo.toml`, `zk/methods/` | Workspace; embeds the guest ELF and image ID | lead |
| `zk/guest/` | Production guest (relations 1 and 2), 11 native tests | Agent A |
| `zk/host/` | `qs-zk` CLI: `image-id`, `prove`, `verify`, `execute`; prove lock; dev-mode refusal; 11 tests | Agent B (verify dev-mode refusal added by lead after review) |
| `fl/zk_reference.py` | Independent pure-Python reference of the whole relation | Agent C |
| `zk/bridge/` (`cli.py`, `vectors.py`, `tests/`, `vectors/`) | Python bridge to the CLI, vector generator (86 vectors), tests | Agent C |
| `tests/zk/` | Negative, positive and cross-check tests against the real binary and a real receipt | Agent D |
| `experiments/zk/` | Benchmark harness | Agent D |
| `pq/envelope.py`, `pq/policy.py`, `pq/zkpolicy.py`, `pq/session.py` | Envelope v2 with `proof_hash`; aggregator proof policy | lead |
| `configs/phase3.yaml`, `experiments/run_phase3.py`, `zk/crosscheck.py`, `Makefile` (`phase3`, `zk-build`, `zk-crosscheck`) | Config, FL integration experiment, cross-check script | lead |
| `tests/test_envelope_v2.py` | Policy-logic tests (use a recording stub, labelled; not a verifier) | lead |
| `docs/zk_status/agent_{a,b,c,d}.md` | Agent status files | agents |

A read-only review agent examined the guest, policy, host and tests; its findings and what was done are under "Review" below.

## Relation actually proved (relation 1)
(a) `SHA256("QSFL-upd" ‖ Δ ‖ nonce) == C`; (b) `‖Δ‖² ≤ B2` computed exactly (all |Δᵢ| < 2²⁵); (c) `SHA256(W_t) == H(W_t)`, sample indices derived in-guest from the public seed, each sampled record Merkle-opened to R with a strict-length path, K = 4 SGD steps of batch 8 giving `W_K − W_t == Δ` exactly. Overflow rule: the guard in `docs/zk_interface.md` §4 (max|a|·max|b|·terms < 2⁶²) — a conservative form of the statement's "intermediate ≥ 2⁶²" rule. Journal = the 146 public bytes (t, c, n_c, K, batch, seed, lr_fx, B2, H(W_t), C, R).

## Commands and real output
```
$ cd zk && cargo build --release                      # guest + host; image id below
$ zk/target/release/qs-zk image-id
c66b4507dff763d1eec563ee5db435490b15ac98bb962cb1c973e498c5360a10

$ .venv/bin/python -m zk.crosscheck                   # every vector through the real guest (executor, no proof) vs Python reference
vectors=86 guest_accept=34 reference_accept=34 mismatches=0

$ cd zk/guest && cargo test --release                 # 11 passed
$ cd zk && cargo test --release                       # host: 11 passed
$ .venv/bin/python -m pytest -q                       # whole repo, includes the real-proof tests
227 passed in 44.80s
$ .venv/bin/python -m pytest -m "not real_proof" -q   # 208 passed (7m37s while a prover was running)
$ .venv/bin/python -m pytest -m real_proof -v tests/zk   # 19 passed in 385.54s (Agent D; one real proof, 377 s)
```
The 227-test run above reused the cached receipt of that real proof (`demo/results/zk/test_cache/`), so it did not prove again. Test counts: 227 in total; 95 of them are the Phase 1/2 tests, tests/zk has 116 (97 need no receipt, 19 use the real receipt), the rest are bridge tests (36), the v2 policy tests (9) and others. The `-m "not real_proof"` count of 208 was taken before the last host change; 227 = 208 + 19.

```
$ make phase3          # experiments.run_phase3 --config configs/phase3.yaml (4 real proofs, 1980 s)
image_id=c66b4507... K=4 batch=8 B=0.9482 honest=[0, 1] attacker=4
round 0 client 0 honest   admitted prove_s=379.7  check=0.19 s receipt=3,058,804 B ‖Δ‖=0.507
round 0 client 1 honest   admitted prove_s=491.2  check=0.30 s receipt=3,058,804 B ‖Δ‖=0.468
round 0 client 4 attacker x50 dropped: guest cannot prove (‖Δ‖²/B² = 427.7); no proof_hash -> bad_proof:missing_proof_hash
round 0 aggregate [0,1] accuracy 0.3008  model_hash_equal_to_non_zk=True
round 1 client 0 honest   admitted prove_s=494.9  check=0.28 s receipt=3,024,116 B ‖Δ‖=0.372
round 1 client 1 honest   admitted prove_s=610.4  check=0.22 s receipt=3,058,804 B ‖Δ‖=0.349
round 1 client 4 attacker x50 dropped (‖Δ‖²/B² = 295.0)
round 1 aggregate [0,1] accuracy 0.4123  model_hash_equal_to_non_zk=True
$ python -m experiments.zk.bench --config configs/phase3.yaml     # 2 real proofs
```
Outputs: `demo/results/phase3_fl.csv`, `demo/results/zk_bench.csv/.md`, receipts in `demo/results/zk/`.

## Cost table (real proofs, composite, po2 = 18, K = 4, batch 8)
Hardware as above. Peak memory = max RSS of the `r0vm` prover child.

| source | prove time | verify (CLI, incl. process start) | receipt | cycles total / user | segments | peak RSS |
|---|---|---|---|---|---|---|
| lead, first `qs-zk prove` | 381.9 s | 0.17 s | 3,058,804 B | 3,014,656 / 2,127,722 | 12 | 2.42 GB |
| Agent D test fixture | 377.3 s | 0.18 s | 3,058,804 B | same | 12 | 2.42 GB |
| benchmark run 0 / run 1 | 402.0 s / 393.4 s | 0.238 s / 0.222 s | 3,058,804 B | same | 12 | 2.36 GB |
| aggregator check (`Session.admit`: hybrid signatures + commitment + proof_hash + real verify) | 0.20 s | | | | | |

Benchmark median prove time 397.7 s (2 runs, composite). In the FL integration run, proofs took 380–610 s (the slower ones ran while other work was using the machine), so **time varies by about 1.6x on this machine**; the table above is the quiet-machine range. Earlier measurements with the unoptimised probe guest (`docs/zk_cost.md`): K = 1, batch 32 took 981 s; K = 2, batch 4 took 377 s; commitment + norm only took 68 s. The optimised guest needs about 2.7x fewer cycles (K = 2, batch 4: 2.14M → 0.79M user cycles). K = 20, batch 32 with the optimised guest was not run; by cycle scaling it is roughly 20 × 1.9M ≈ 37M user cycles, about 1.5–2 hours per proof (an extrapolation, not a measurement). A po2 = 20 attempt (probe guest) was killed for lack of memory; po2 = 19 and succinct receipts were not tried.

## Negative tests (real binary and real receipt; reasons observed)
| case | stage | result |
|---|---|---|
| scaled update ×50 | `qs-zk prove` | exit 3, guest "norm bound" (no receipt exists) |
| scaled ×50, aggregator | `Session.admit` | `bad_proof:missing_receipt` (v2 envelope) / `bad_proof:missing_proof_hash` (v1) |
| wrong commitment | prove | exit 3 "commitment" |
| wrong H(W_t) | prove | exit 3 "model hash" |
| fabricated update: one entry +1, commitment recomputed | prove | exit 3 "delta mismatch" |
| fabricated small random update, commitment recomputed | prove | exit 3 "delta mismatch" |
| wrong Merkle path: flipped sibling / wrong leaf / wrong root R | prove | exit 3 "merkle" |
| Merkle path one sibling short | prove | exit 3 "opening count" |
| wrong round (round-0 envelope in round 1) | Verifier | `wrong_round` (fires before the proof check) |
| wrong round (re-signed round-1 envelope, same receipt) | ZkPolicy | `bad_proof:journal_mismatch` |
| tampered public input: each of 12 fields (relation, t, c, n_c, K, batch, seed, lr_fx, B2, H_w, C, R) | `qs-zk verify` | exit 5 `journal_mismatch` (all 12) |
| tampered receipt bytes (seal middle/early, journal region, last byte) | verify | exit 4 `receipt_invalid` |
| truncated receipt | verify | exit 4 |
| receipt of client 0 in client 1's envelope | `Session.admit` | `bad_proof:journal_mismatch` |
| `proof_hash` of a different receipt | `Session.admit` | `bad_proof:hash_mismatch` |
| v1 envelope under a ZkPolicy | `Session.admit` | `bad_proof:missing_proof_hash` |
| ZkPolicy with signatures `none`, relation ≠ 1, unregistered R, replayed nonce (after review) | policy | refused at construction / `bad_proof:unregistered_root` / `replayed_nonce` before any proof check |
| honest | verify and admit | exit 0; admitted; journal equals reference journal and the signed-envelope-derived expected public; delta bytes and nonce are not substrings of the receipt or journal |

Guest failures happen in the executor before any proving work, so these real `prove` calls fail in seconds.

## Cross-check
`zk.crosscheck`: 86 vectors (34 accept, 52 reject) run through the real guest; accept/reject and the 146 journal bytes equal the independent Python reference on every vector (0 mismatches). The vectors include norm exactly B2 / B2+1, guard at 2⁶² and one below, repeated sample indices, n_c odd/even/1, wrong path lengths, label 10, trailing byte, B2 ≥ 2⁵⁰ and relation-2 cases. 8 honest K = 4, batch 8 vectors (`honest_main_*`) are the real-proof candidates; **two of them were proved and verified** (benchmark), plus the FL-run proofs. The other six honest vectors were cross-checked in the executor only, not proved. Two vectors (`bad_magic`, `empty_blob`) are rejected by the host before the guest (exit 2), so they do not test the guest's own magic/length checks.

## Review (read-only agent) and what changed
No path was found where a false statement passes the guest or an honest one fails. Fixed after review: verifying with dev mode set is refused (host, exit 6); a ZkPolicy with signatures `none` is refused; relation 2 needs an explicit `allow_cut`; ZkPolicy can pin registered roots (`roots=`; used by `run_phase3`); replay checks run before the expensive proof check. Not fixed: untested guest branches for batch ≥ 65536 (not reachable at this size).

## Deviations, decisions, open issues
- **K = 4, batch 8, not K = 20, batch 32** (D-019). Benign accuracy at this size after 10 rounds is about 0.76 on the calibration seed (Phase 1: 0.94), and 0.30 → 0.41 over the two FL-run rounds with 2 clients. B was recalibrated (0.9482). Phase 1/2 configs and results were not changed.
- **FL integration covers 2 rounds and 2 honest clients plus 1 attacker**, not 10 rounds × 5 clients (that would be about 5 hours of proving). Equality with the non-ZK pipeline is for those participants and rounds only (`model_hash_equal_to_non_zk=True` both rounds). Phase 1/2 pipelines with all clients were not re-run with proofs.
- **Envelope v2** adds `proof_hash` (D-018); the nonce is visible in the envelope though the statement lists it as private.
- Guard is the conservative operand-maximum rule (stricter than the statement's wording); it can reject an update whose intermediates never reach 2⁶².
- Only composite receipts, po2 = 18, were measured. 
- `test_no_zkvm_dev_mode_in_repo` (Phase 1) was narrowed to forbid enabling dev mode outside `tests/zk`.
- Timing varies by about 1.6x run to run with background load; memory 2.4 GB is set by po2.

## What is NOT proven (limits, from `docs/zk_statement.md` §5)
- Honesty or provenance of the data: the proof binds to **whatever R the client chose**. A client that committed to flipped labels or a poisoned dataset gets a valid proof. R is checked against a registered root only if the aggregator is given `roots=` (done in `run_phase3`; no enrolment exists).
- In-bound poisoning (small sign-flipped or slow-poisoning updates) is not detected.
- Δ is sent in the clear; the proof hides only the data records, W_t-derived intermediates and the nonce (and the nonce is visible in the envelope).
- Replay: the circuit binds t, C and H(W_t); rejecting resubmission is done by the signed envelope and nonce tracking, not by the circuit.
- `n_c`, K, batch, seed, lr_fx, B2 are trusted aggregator configuration.
- ZK enforcement holds only when signatures ≠ `none`.
- Soundness of RISC Zero itself and its hash-based assumptions are assumed, not shown here; no side-channel analysis.
- The cost figures apply to K = 4, batch 8 only.
