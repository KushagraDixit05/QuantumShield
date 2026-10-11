# Agent C status (reference, vectors, bridge)

## Done
- `fl/zk_reference.py`: independent pure-Python relation (Python-int arithmetic, checked i64 that raises, u128 guard, section 4 step order, sampling, strict Merkle, commitment, model hash, norm, B2 < 2^50, well-formedness). API: `build_input`, `parse_input`, `evaluate(blob) -> (ok, journal, reason)`, `journal_for`, `run_sgd`, `sgd_step`, `sample_indices`, `honest_input`, `merkle_root_and_paths`, `commit`, `model_hash`. No floats.
- `zk/bridge/vectors.py`: `python -m zk.bridge.vectors --config configs/phase3.yaml --out zk/bridge/vectors/` -> 86 vectors in `zk/bridge/vectors/` (`<name>.in.bin`, `<name>.expect.json` with ok, reason, journal_hex, relation, K, batch). Deterministic (tested). The generator asserts every vector's verdict equals the verdict it was designed for.
- `zk/bridge/cli.py`: `execute(blob)`, `prove_update(blob, receipt_path, journal_path, po2=18, kind='composite')`, `verify_receipt(receipt_bytes, expected_public) -> (ok, reason)` (reasons ok, guest_failed, receipt_invalid, journal_mismatch, bad_input, refused, binary_missing, timeout, error_N), `image_id()`, `client_blob(...)`, `client_prove(...)`; binary `zk/target/release/qs-zk` or env `QS_ZK_BIN`. `prove_update` raises `ZkError(reason)`; I never called `qs-zk prove`.
- Tests in `zk/bridge/tests/` (no proving).

## Files
fl/zk_reference.py, zk/bridge/{__init__,cli,vectors}.py, zk/bridge/tests/{__init__,test_reference,test_bridge}.py, zk/bridge/vectors/*. `zk/__init__.py` already existed and was not touched.

## Honest vectors for real proofs (config K=4 batch=8, B=0.9482, relation 1; D-019)
honest_main_s0_t0_c0, _s0_t0_c1, _s0_t1_c2, _s0_t3_c3, _s0_t9_c4, _s1_t2_c0, _s2_t5_c1, _s0_t4_c2 (all accept with B2 = bound_sq(0.9482)), plus honest_cfg. Small-K honest vectors keep their names (honest_k1b1, honest_k3b2, honest_k1b32, honest_k2b8, honest_nc*_k2b4, repeated_idx_*). All reject/mutation vectors use the config K/batch; boundary vectors (norm exactly B2 and B2-1 on the honest delta) use the new norms.

## Cross-check against the real guest
`.venv/bin/python -m zk.crosscheck`: vectors=86 guest_accept=34 reference_accept=34 mismatches=0 (interface v1.3: guest enforces K=batch=0 for relation 2; stale k2b4 main vectors were deleted by the regeneration).

## Reference vs fl.client.local_train
Identical delta for 12 seeds x varied (K, batch, client, round, lr, perturbed model). Documented divergence: `fixedpoint._maxabs` uses `np.abs`, which maps int64 min to itself (negative), so the Phase 1 guard passes for a weight of -2^63 and the product wraps; the reference raises `guard`. Also `pre = ... + b1`, `out = ... + b2`, `dout = out - target`, sums and `w - fx_mul` are unchecked in numpy (wrap) but checked in the reference (vector `overflow_checked_add`). Neither occurs in honest runs.

## Blocked
Nothing. Real receipts are not produced by me (lead schedules).

## Needs from others
- (resolved in interface v1.3: relation 2 requires K = batch = 0, opening is 512 bytes, no n_open for relation 2)
- Agent B: `qs-zk verify` must return 4 / 5 as in section 9; I only mocked this (fake script, plumbing only), not exercised against a real receipt.

## Ambiguities in docs/zk_interface.md
1. Opening layout says `512 x (64 x i64)`; I read it as 512 bytes (= 64 x i64), per the lead's make_input.py (size 4 + 512 + 4 + 32d).
2. Relation 2: the table lists `n_open (0 when relation = 2)` but the text says openings are absent. I follow make_input.py and the text: no n_open field at all, blob ends after delta; any extra byte is trailing_bytes.
3. Order of checks is unspecified; only accept/reject is fixed. Reasons in `expect.json` are the reference's tags, not guest panic text.
4. Label >= 10 check happens at use (SGD), after the Merkle checks, in the reference; verdict is identical either way.
5. "B2 < 2^50" vs entry cap 2^25: entry |d| = 2^25 already gives d^2 = 2^50 > B2, so the cap is redundant; kept for parity.
6. `t` and `c` are u32 and `seed` u64 in sampling, `lr_fx` is signed; n_c is not bounded above except by the blob length.

## Vector list
| name | expected | reason | params |
|---|---|---|---|
| K_zero | reject | bad_K | rel 1 K=0 b=8 |
| b2_2pow50_minus1_accept | accept | ok | rel 1 K=4 b=8 |
| b2_2pow50_reject | reject | b2_too_large | rel 1 K=4 b=8 |
| b2_max_reject | reject | b2_too_large | rel 1 K=4 b=8 |
| bad_magic | reject | bad_magic | rel 1 K=4 b=8 |
| bad_version | reject | bad_version | rel 1 K=4 b=8 |
| batch_not_pow2 | reject | bad_batch | rel 1 K=4 b=3 |
| batch_zero | reject | bad_batch | rel 1 K=4 b=0 |
| empty_blob | reject | truncated | rel None K=None b=None |
| guard_at_2pow62 | reject | guard | rel 1 K=1 b=1 |
| guard_below_2pow62 | accept | ok | rel 1 K=1 b=1 |
| guard_below_cfg | accept | ok | rel 1 K=4 b=8 |
| guard_lr_huge | reject | guard | rel 1 K=4 b=8 |
| guard_neg_at_2pow62 | reject | guard | rel 1 K=1 b=1 |
| guard_neg_below | accept | ok | rel 1 K=1 b=1 |
| guard_w1_i64max | reject | guard | rel 1 K=1 b=1 |
| honest_cfg | accept | ok | rel 1 K=4 b=8 |
| honest_k1b1 | accept | ok | rel 1 K=1 b=1 |
| honest_k1b32 | accept | ok | rel 1 K=1 b=32 |
| honest_k2b8 | accept | ok | rel 1 K=2 b=8 |
| honest_k3b2 | accept | ok | rel 1 K=3 b=2 |
| honest_main_s0_t0_c0 | accept | ok | rel 1 K=4 b=8 |
| honest_main_s0_t0_c1 | accept | ok | rel 1 K=4 b=8 |
| honest_main_s0_t1_c2 | accept | ok | rel 1 K=4 b=8 |
| honest_main_s0_t3_c3 | accept | ok | rel 1 K=4 b=8 |
| honest_main_s0_t4_c2 | accept | ok | rel 1 K=4 b=8 |
| honest_main_s0_t9_c4 | accept | ok | rel 1 K=4 b=8 |
| honest_main_s1_t2_c0 | accept | ok | rel 1 K=4 b=8 |
| honest_main_s2_t5_c1 | accept | ok | rel 1 K=4 b=8 |
| honest_nc16_k2b4 | accept | ok | rel 1 K=2 b=4 |
| honest_nc1_k1b1 | accept | ok | rel 1 K=1 b=1 |
| honest_nc1_k2b4 | accept | ok | rel 1 K=2 b=4 |
| honest_nc2_k2b4 | accept | ok | rel 1 K=2 b=4 |
| honest_nc3_k2b4 | accept | ok | rel 1 K=2 b=4 |
| honest_nc4_k2b4 | accept | ok | rel 1 K=2 b=4 |
| honest_nc5_k2b4 | accept | ok | rel 1 K=2 b=4 |
| honest_nc7_k2b4 | accept | ok | rel 1 K=2 b=4 |
| honest_nc9_k2b4 | accept | ok | rel 1 K=2 b=4 |
| label_10 | reject | label_range | rel 1 K=1 b=1 |
| lr_negative | reject | bad_lr | rel 1 K=4 b=8 |
| lr_zero | reject | bad_lr | rel 1 K=4 b=8 |
| merkle_flipped_sibling_bit | reject | bad_merkle_path | rel 1 K=4 b=8 |
| merkle_flipped_top_sibling_bit | reject | bad_merkle_path | rel 1 K=4 b=8 |
| merkle_path_too_long_first | reject | trailing_bytes | rel 1 K=4 b=8 |
| merkle_path_too_long_last | reject | trailing_bytes | rel 1 K=4 b=8 |
| merkle_path_too_short_last | reject | truncated | rel 1 K=4 b=8 |
| merkle_wrong_label | reject | bad_merkle_path | rel 1 K=4 b=8 |
| merkle_wrong_leaf_data | reject | bad_merkle_path | rel 1 K=4 b=8 |
| merkle_wrong_root | reject | bad_merkle_path | rel 1 K=4 b=8 |
| n_c_claimed_larger | reject | bad_opening_count | rel 1 K=4 b=8 |
| n_open_huge | reject | truncated | rel 1 K=4 b=8 |
| nc_zero | reject | bad_n_c | rel 1 K=4 b=8 |
| norm_B2_plus1_reject | reject | norm_exceeded | rel 1 K=4 b=8 |
| norm_exact_B2_accept | accept | ok | rel 1 K=4 b=8 |
| norm_over_small_B2 | reject | norm_exceeded | rel 1 K=4 b=8 |
| opening_duplicate_extra | reject | bad_opening_count | rel 1 K=4 b=8 |
| opening_index_out_of_range | reject | opening_index_mismatch | rel 1 K=4 b=8 |
| opening_missing | reject | bad_opening_count | rel 1 K=4 b=8 |
| openings_first_two_swapped | reject | opening_index_mismatch | rel 1 K=4 b=8 |
| openings_none | reject | bad_opening_count | rel 1 K=4 b=8 |
| openings_reversed | reject | opening_index_mismatch | rel 1 K=4 b=8 |
| overflow_checked_add | reject | overflow | rel 1 K=1 b=1 |
| rel2_K_nonzero | reject | bad_params | rel 2 K=2 b=0 |
| rel2_bad_commitment | reject | commitment_mismatch | rel 2 K=0 b=0 |
| rel2_batch_nonzero | reject | bad_params | rel 2 K=0 b=4 |
| rel2_entry_at_cap_reject | reject | norm_entry_cap | rel 2 K=0 b=0 |
| rel2_entry_below_cap_accept | accept | ok | rel 2 K=0 b=0 |
| rel2_entry_neg_below_cap_accept | accept | ok | rel 2 K=0 b=0 |
| rel2_entry_neg_cap_reject | reject | norm_entry_cap | rel 2 K=0 b=0 |
| rel2_honest_delta | accept | ok | rel 2 K=0 b=0 |
| rel2_norm_exact_accept | accept | ok | rel 2 K=0 b=0 |
| rel2_norm_plus1_reject | reject | norm_exceeded | rel 2 K=0 b=0 |
| rel2_small | accept | ok | rel 2 K=0 b=0 |
| rel2_trailing_byte | reject | trailing_bytes | rel 2 K=0 b=0 |
| relation_3 | reject | bad_relation | rel 3 K=4 b=8 |
| repeated_idx_nc2_k3b8 | accept | ok | rel 1 K=3 b=8 |
| repeated_idx_nc3_k4b4 | accept | ok | rel 1 K=4 b=4 |
| trailing_byte | reject | trailing_bytes | rel 1 K=4 b=8 |
| truncated_one_byte | reject | truncated | rel 1 K=4 b=8 |
| wrong_commitment | reject | commitment_mismatch | rel 1 K=4 b=8 |
| wrong_delta_minus1_last_recommitted | reject | delta_mismatch | rel 1 K=4 b=8 |
| wrong_delta_plus1_recommitted | reject | delta_mismatch | rel 1 K=4 b=8 |
| wrong_delta_plus1_stale_commitment | reject | commitment_mismatch | rel 1 K=4 b=8 |
| wrong_model_hash | reject | model_hash_mismatch | rel 1 K=4 b=8 |
| wrong_nonce | reject | commitment_mismatch | rel 1 K=4 b=8 |
| wrong_wt_consistent_hash_stale_delta | reject | delta_mismatch | rel 1 K=4 b=8 |

## pytest output
```
....................................                                     [100%]
36 passed in 10.28s

full suite: 107 passed
```
