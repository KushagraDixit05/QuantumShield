# Agent A status: production guest (zk/guest)

## Done
Full relation 1 and relation 2 per docs/zk_interface.md (incl. v1.3: relation 2 has no n_open field, K and batch must be 0, trailing bytes are an error; opening x is 512 bytes). Integer only, no float, no dev-mode reference. Built through the workspace (`cd zk && flock -x ../.zk_build.lock cargo build --release`); `qs-zk execute` runs all test vectors with journal == input[0..146]; a tampered blob exits 3 (`guest-failed: model hash`). No prover was run.

## Files (all under zk/guest/)
- `Cargo.toml` (package qs_guest, own [workspace], lib `qs_core` + bin `qs_guest`, deps risc0-zkvm 3.0.6 default-features=false ['std'], bytemuck)
- `src/main.rs` (thin: env::read u32 length, env::read_slice words, call `qs_core::run`, commit 146-byte journal or panic with message)
- `src/lib.rs` (`run`: header, hashes, norm, sampling loop, openings, K steps, delta check), `input.rs`, `fixed.rs` (guard), `sgd.rs` (step), `merkle.rs`, `sample.rs`, `sha.rs`
- `tests/vectors.rs`, `tests/data/*.bin` (vectors made with the Python reference code: fl.client/fl.merkle/fl.model/pq.envelope; n_c in {1,2,3,5,7,8,100}, K/batch {2/4, 3/1, 1/32}, real digits data, relation 2)

## Semantics notes
- Guard: exact rule max|a|*max|b|*terms < 2^62 (u128). For speed a cheap sufficient test runs first (OR of one's-complement magnitudes gives |v| <= bound+1); only if it fails is the exact maximum computed, so outcomes are identical to the exact rule (tested at the 2^62 boundary, incl. i64::MIN).
- After the guard passes, accumulation uses wrapping adds (cannot overflow). Other adds/subs (bias add, out-target, bias sums, W update, W_K-W_t) are checked. The W update has a fused fast path used only when a-priori bounds prove no overflow (g fits i32, |lr*g|<2^46, |w|<2^62); otherwise the checked path runs. Both verified against an independent i64/i128 reference in tests (narrow, wide and guard-failing regimes).
- Norm: per-entry |d|<2^25 test then u64 sum (exact: 2410 * 2^50 < 2^62), equivalent to the u128 sum.
- Order of checks differs from the doc's order but every check is a hard failure, so the pass/fail set is the same.
- Dedup of indices is first-appearance, linear search; opening must carry that index; all n_open consumed; label < 10 on every opening; exactly depth siblings.

## Cycles (qs-zk execute, user_cycles; total in brackets)
| input | probe (lead's zk_cost.md) | now |
|---|---|---|
| K=2, batch 4 (real data, n_c=288) | 2,140,066 (2,899,968) | 793,502 (1,179,648) |
| K=1, batch 32 | 5,049,585 (6,553,600) | 1,866,553 (2,490,368) |
| relation 2 | 325,115 (524,288) | 105,247 (262,144) |
Intermediate: 992k / 2.20M after first rewrite, then 905k / 1.93M with a 2-multiply 32x32->64 product (inline `mulh`), then fused shift+update.
Breakdown at K=2, batch 4 (per step ~285k): forward layer 1 plus weight bounds ~98k, accumulate gW1/gW2 ~66k, fused shift+multiply+update ~56k, rest small. Fixed part before sampling ~149k (hash 2 x 302 blocks, copies, norm). Each opening ~9.3k (leaf 9 blocks plus 9 nodes). Total/user ratio is about 1.5 because each segment pays page-in for the working set (w, g, buffers); fewer, larger segments would reduce that overhead.
Ideas not done: process two W1 rows per x load (~4%), build Merkle node blocks without memcpy/memset (~3%), per-k compaction for gW1 (~5%).

## Test output (cargo test --release, CARGO_TARGET_DIR=zk/target-guest)
```
running 11 tests
test merkle_depths ... ok
test guard_boundary ... ok
test floor_shift_on_negatives ... ok
test sampling_index_matches_python ... ok
test sha_known_answers ... ok
test rel2_rules ... ok
test missing_sibling_is_rejected ... ok
test norm_bound_boundary ... ok
test negatives_rel1 ... ok
test step_matches_reference_narrow_and_wide ... ok
test vectors_pass ... ok
test result: ok. 11 passed; 0 failed
```
Covers: SHA-256 (empty, abc, 517-byte leaf), sampling index vs fl.client.sample_indices, Merkle for n_c=1 (depth 0), even and odd n_c, strict path length/trailing/short, floor shift on negatives (negative X and weights in the vectors and step-vs-reference), guard boundary (2^62 fails, one below passes), norm bound boundary (B2 = norm passes, norm-1 fails; |d|=2^25 rejected), label>=10, opening order/count, relation 2 rules.

## Blocked
Nothing. No real proof generated (not allowed); ask the lead if one is wanted at the new cycle count.

## Needs from others
- Lead: docs/zk_cost.md and D-017 sizing are now pessimistic: K=1 batch 32 costs 2.49M total cycles (was 6.55M) and K=2 batch 4 costs 1.18M (was 2.90M). Re-measure with a real proof before changing the decision.

## Interface ambiguities found
1. Opening layout says `512 x (64 x i64)`: read as 512 bytes (fixed in v1.3).
2. Relation 2 n_open field (fixed in v1.3: absent).
3. The interface does not say whether `lr_fx > 0` applies to relation 2; the guest enforces it for both (as section 7 lists it under "Always").
4. Bytes 146..178 (nonce) are private but sit inside the "public" 0..178 prefix; the journal is bytes 0..146 only (as written). Fine, just noting.
