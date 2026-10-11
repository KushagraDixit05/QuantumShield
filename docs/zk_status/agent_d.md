# Agent D status (tests/zk, experiments/zk)

## Done
- tests/zk: negative, positive, tamper, cross-check tests against the real `qs-zk` binary and real receipt. No stubs, no dev mode (none of my files sets it; `test_no_zkvm_dev_mode_in_repo` passes).
- experiments/zk: benchmark harness with `--dry` (execute only), `--kinds`. NOT run for real (lead schedules).
- Markers registered in tests/zk/conftest.py `pytest_configure`: `real_proof`, `prover_cli`, `slow`, `dev_mode`. `slow` is unused (cross-check of 86 vectors takes ~5 s total).
- `prover_cli` = real `qs-zk prove` on a false statement: exit 3 in the executor, no proving work, but it takes the prove lock first (waits if another prover runs).

## Files
tests/zk/conftest.py, test_zk_negative.py, test_zk_receipt.py, test_zk_crosscheck.py;
experiments/zk/__init__.py, bench.py, bench.yaml (`base: configs/phase3.yaml`, `bench:` section).
Honest receipt cache: demo/results/zk/test_cache/<sha256(image_id||blob)[:20]>.{receipt,journal,stats.json}.

## Proofs used: exactly 1 real proof
Client 0, round 0, W = model.init(0), K=4 batch=8 lr 0.3, B=0.9482, po2 18, composite, image id c66b4507dff763d1...
prove_s 377.31 (6.3 min), verify_s 0.184, cycles 3,014,656, user_cycles 2,127,722, 12 segments, receipt 3,058,804 B, peak RSS 2,424,724 kB.
Every test in test_zk_receipt.py reuses that receipt (fixture `honest`); later runs reuse the cache (no new proof).
Tests that prove nothing: all test_zk_negative.py (execute fails before proving), cross-check.

## Rejection table
| case | where | result |
|---|---|---|
| scaled x50 (C recomputed) | `qs-zk prove` | exit 3, guest "norm bound" |
| scaled x50, aggregator | Session.admit | v2 env, no receipt: bad_proof:missing_receipt; v1 env: bad_proof:missing_proof_hash |
| C random / wrong nonce | prove | exit 3 "commitment" |
| H_w wrong (extra) | prove | exit 3 "model hash" |
| delta+1 at one entry, C recomputed | prove | exit 3 "delta mismatch" |
| small random delta, C recomputed | prove | exit 3 "delta mismatch" |
| flipped sibling bit | prove | exit 3 "merkle" |
| leaf x changed, real path | prove | exit 3 "merkle" |
| wrong root R | prove | exit 3 "merkle" |
| path one sibling short | prove | exit 3 "opening count" (layout shifts; reference says truncated) |
| each of 12 public fields changed (relation,t,c,n_c,K,batch,seed,lr_fx,B2,H_w,C,R) | verify | exit 5 journal_mismatch (all 12) |
| flip byte in seal (middle, early), journal region, last byte | verify | exit 4 receipt_invalid (invalid proof / claim digest mismatch / invalid format) |
| truncated receipt | verify | exit 4 (undecodable) |
| receipt of client 0 in client 1 envelope | Session.admit | bad_proof:journal_mismatch |
| proof_hash of a different (byte-flipped) receipt | Session.admit | bad_proof:hash_mismatch |
| v1 envelope under ZkPolicy | Session.admit | bad_proof:missing_proof_hash |
| wrong round, round-0 envelope in round 1 | Verifier | wrong_round (fires first, ZkPolicy never reached) |
| wrong round, round-1 re-signed envelope, same nonce (only t differs) | ZkPolicy | bad_proof:journal_mismatch |
| wrong round, natural round-1 envelope (t and C differ) | ZkPolicy | bad_proof:journal_mismatch |
| honest | verify / Session.admit (hybrid) | exit 0 / admitted in 0.18 s; journal == reference journal == blob[:146] == expected_public from signed envelope; delta bytes (first 64 B) and nonce not in receipt nor journal |

## Test output
Non-real-proof (whole repo, `pytest -m "not real_proof" -q`): `204 passed, 19 deselected in 32.46s` (tests/zk part: 97 passed in 4.9 s).
Real proof (`pytest -m real_proof -v -s tests/zk`): `19 passed, 97 deselected in 385.54s (0:06:25)`; proof fixture setup 377.74 s; each tamper-public verify test ~0.54 s; wrong-round 0.38 s; tamper-receipt 0.31 s. Printed rejection lines are in the table above (from the run).

## Benchmark dry run (execution only, NOT proving)
`python -m experiments.zk.bench --config configs/phase3.yaml --dry`: honest_main_s0_t0_c0 and _c1 relation holds, journal = blob head, 12 segments, cycles 3,014,656, wall 0.08 s. The aggregator-check path (agg_check) was only exercised with junk receipt (reaches real verify, bad_proof:receipt_invalid); its success path is exercised by the tests and will be by the real run.

## Blocked
Nothing.

## Needs from others
- Nothing required. Note: `pytest.ini` options in pyproject have no markers; I register them in tests/zk/conftest.py only, so `-m` selection works but `--strict-markers` would need them registered there too (they are).
- Lead: run `python -m experiments.zk.bench --config configs/phase3.yaml` when scheduling a prover (2 proofs, ~13 min). `--kinds composite,succinct` only if wanted.
