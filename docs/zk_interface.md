# ZK interface contract (Phase 3)

Status: shared contract for the guest (`zk/guest/`), host CLI (`zk/host/`), Python reference and bridge (`fl/zk_reference.py`, `zk/bridge/`) and tests. It implements `docs/zk_statement.md` §1-§4. Do not change this file without telling the lead and recording why in the change log at the bottom.

All integers are little-endian. "fails" means the guest panics: no receipt exists. All arithmetic is integer; no float type may appear in the guest or in the reference's relation code.

## 1. Relations
`relation` byte: `1` = full relation (a)+(b)+(c). `2` = commitment + norm only (cut-ladder fallback, used only if the lead records it in `decisions.md`). The relation byte is part of the journal, so a verifier cannot confuse the two.

## 2. Guest input (one raw byte blob)
`read_frame`/`write_frame` are unstable in risc0-zkvm 3.0.6, so the blob travels as: `builder.write(&(len as u32))` (serde, 1 word), then `builder.write_slice(&words)` where `words` is the blob zero-padded to a multiple of 4 bytes and reinterpreted as little-endian `u32`. The guest does `let n: u32 = env::read(); env::read_slice(&mut words[..ceil(n/4)])` and truncates to `n` bytes. Python builds the plain blob; only the host does the length/padding step. Padding bytes are never part of the blob.

```
off  size  field
0    4     magic  = b"QSZK"
4    1     version = 1
5    1     relation (1 or 2)
6    4     t            round
10   4     c            client id
14   4     n_c          dataset size (>= 1)
18   4     K            SGD steps (>= 1; ignored but must be 0 when relation = 2)
22   4     batch        power of two, >= 1 (0 when relation = 2)
26   8     seed         u64
34   8     lr_fx        i64, fixed point learning rate (> 0)
42   8     B2           u64, ||Δ||^2 bound in 2^-32 units (must be < 2^50)
50   32    H_w          claimed SHA256(W_t)
82   32    C            commitment
114  32    R            Merkle root
146  32    nonce        private
178  19280 W_t          2410 x i64   (private; omitted when relation = 2)
...  19280 delta        2410 x i64   (private)
...  4     n_open       number of openings (0 when relation = 2)
...  n_open x opening
```
Opening (variable length, depth `d = ceil(log2(n_c))`, 0 when `n_c = 1`):
```
4 index u32 | 512 bytes (x = 64 x i64) | 4 label u32 | d x 32 sibling hashes (leaf level first)
```
If `relation = 2` the `W_t` section, the `n_open` field and the openings are all absent (not zero-filled), and the header fields `K` and `batch` must be 0 (the guest fails otherwise, so the journal for relation 2 is unambiguous). Trailing bytes after the last opening are an error.

## 3. Journal (146 bytes, committed with `env::commit_slice`)
```
0   4  b"QSZK"
4   1  version = 1
5   1  relation
6   4  t
10  4  c
14  4  n_c
18  4  K
22  4  batch
26  8  seed
34  8  lr_fx
42  8  B2
50  32 H_w
82  32 C
114 32 R
```
That is exactly the public part of the input in the same order and encoding (bytes 0..146 of the input). Anything the verifier is not told about (Δ, nonce, W_t, records, paths) is not in the journal. The aggregator verifies a receipt against the image ID and then requires `journal == expected_public` byte for byte, where `expected_public` is built from the signed envelope and the round state (§8).

## 4. Fixed-point rules (exactly `fl/fixedpoint.py`, `fl/model.py`, `fl/client.py`)
`SCALE_BITS = 16`, `ONE = 1<<16`, `LIMIT = 1<<62`. `>>` is an arithmetic shift (floor toward -inf) on i64.

**Checked arithmetic.** Every `+`, `-`, unary minus and accumulation is checked i64: overflow of i64 fails (the Python reference raises; it must not wrap).

**Guard (this is what "any intermediate >= 2^62" means in the implementation).** Before every product-sum call, compute `ma = max|a|` over the whole left operand and `mb = max|b|` over the whole right operand (both are the full arrays passed to that call, in u128), and fail if `ma * mb * terms >= 2^62`. `terms` is the shared inner dimension. The guard is a conservative check on operand maxima, as in `fixedpoint._guard`; it is the relation. When it passes, the exact i64 accumulation cannot overflow.

Primitive ops:
- `sum_prod_shift(A, B)` = `(A @ B) >> 16`, guard terms = `A.shape[-1]`.
- `fx_mul(a, b)` = `(a*b) >> 16` elementwise, guard terms = 1.

Model: `W` = `W1 (32x64 row-major) | b1 (32) | W2 (10x32 row-major) | b2 (10)`, 2,410 values. D_IN = 64, D_H = 32, D_OUT = 10.

One SGD step on batch `X (B,64)`, `y (B)` (all labels must be `< 10`, else fail), `shift = log2(B)`:
1. `pre = sum_prod_shift(X, W1ᵀ) + b1` (broadcast add per row). Guard on `(X, W1)`, terms 64.
2. `h = max(pre, 0)`.
3. `out = sum_prod_shift(h, W2ᵀ) + b2`. Guard on `(h, W2)`, terms 32.
4. `dout = out - target`, `target[i, y_i] = ONE`, else 0.
5. `dh = sum_prod_shift(dout, W2) * (pre > 0)`. Guard on `(dout, W2)`, terms 10. The mask multiplies by 0 or 1.
6. `gW2 = sum_prod_shift(doutᵀ, h) >> shift`. Guard on `(dout, h)`, terms B.
7. `gW1 = sum_prod_shift(dhᵀ, X) >> shift`. Guard on `(dh, X)`, terms B.
8. `gb1 = (sum over batch of dh) >> shift`, `gb2 = (sum over batch of dout) >> shift`. Plain checked sums.
9. `g = flatten(gW1, gb1, gW2, gb2)`; `W <- W - fx_mul(lr_fx, g)`. Guard `(lr_fx, g)`, terms 1.

`Δ = W_K - W_t` (checked subtraction). The guard maxima are taken over the arrays exactly as listed (the transposed operands contain the same values, so the maximum is unchanged).

Inputs: pixel `p` is stored as `p << 12`. The guest does not check that the record `x` values are in that range: they are whatever is committed under `R` (statement §5).

## 5. Sampling
For step `s` in `0..K`, slot `j` in `0..batch`: `idx[s][j] = u64_le(SHA256(b"QSFL-idx" || seed u64 || t u32 || c u32 || s u32 || j u32)[0:8]) mod n_c`. Step `s` uses records `idx[s][0..batch]` in slot order.

## 6. Merkle (exactly `fl/merkle.py`)
- Leaf bytes: `x` as 64 x i64 LE (512 B) `|| y` as u32 LE. Leaf hash `= SHA256(0x00 || leaf bytes)`.
- Node: `SHA256(0x01 || left || right)`.
- Tree over `n_c` leaves: at each level, if the level length is odd the last node is duplicated; repeat until one node. Depth `d = ceil(log2(n_c))`, `d = 0` for `n_c = 1`.
- Verification of index `i`: `h = leaf hash`; for each sibling `sib` (leaf level first): if `i` even, `h = node(h, sib)` else `h = node(sib, h)`; `i //= 2`. Accept iff `h == R`. **Stricter than `merkle.verify`:** the path must have exactly `d` siblings, and `i < n_c`.
- Openings are unique by index. The guest walks `(s, j)` in order; the first time an index appears, it consumes the next opening, which must carry exactly that index. Later occurrences reuse the verified record. All openings must be consumed (`n_open` = number of distinct indices, in first-appearance order). Honest provers cannot alter which record a slot reads, because the index is derived inside the guest.

## 7. The relation (what the guest checks)
Always (both relations):
1. Input well formed (magic, version, lengths, `B2 < 2^50`, `lr_fx > 0`, `n_c >= 1`).
2. (a) `SHA256(b"QSFL-upd" || Δ as i64 LE || nonce) == C`.
3. (b) `max|Δ_i| < 2^25` and `sum Δ_i^2 <= B2`, the sum in u128 (exact). Because `B2 < 2^50`, any entry with `|Δ_i| >= 2^25` already breaks the bound, so the first test only mirrors `fixedpoint.norm_sq`.

If `relation = 1`:
4. (c) `SHA256(W_t as i64 LE) == H_w`; `K >= 1`; `batch` is a power of two; sampling per §5; every sampled record opens to `R` per §6; K steps per §4 from `W_t` give `W_K`; `W_K - W_t == Δ` for all 2,410 entries.

Not checked, by design (statement §5): honesty or provenance of the data under `R`; that `round t` is the current round; replay. Those belong to the envelope and aggregators.

## 8. Binding to the Phase 2 envelope (v2) and verifier behaviour
Envelope v2 update payload = v1 payload followed by `proof_hash` (32 B) = `SHA256(receipt bytes)`, where receipt bytes is the file the CLI writes (`bincode` of the RISC Zero `Receipt`). The aggregator:
1. verifies the envelope signature(s) as in Phase 2;
2. checks `SHA256(receipt bytes) == proof_hash`;
3. verifies the receipt against the guest image ID;
4. builds `expected_public` (§3) from: envelope `round`, `client_id`, `H(W_t)`, `C`, `R`, and from the run configuration `n_c` (known for client `c` from its registered dataset size), `seed`, `K`, `batch`, `lr_fx`, `B2`; and requires `journal == expected_public`.
Any failure drops the update with reason `bad_proof` (hash mismatch, receipt invalid, or journal mismatch are separate sub-reasons). `n_c` is trusted configuration in the MVP (no enrolment, statement §5).

## 9. Host CLI (`qs-zk`, built by `zk/host/`)
```
qs-zk image-id                                  -> prints the guest image ID, 64 hex chars
qs-zk prove  --input in.bin --receipt r.bin --journal j.bin [--po2 N] [--kind composite|succinct] [--stats stats.json]
qs-zk verify --receipt r.bin --expect pub.bin [--journal-out j.bin]
qs-zk execute --input in.bin --journal j.bin [--stats stats.json]   # runs the guest in the zkVM executor only: no proof, no lock, seconds
```
`execute` is for cross-checks and for finding out quickly whether the relation holds (exit 3 when the guest fails). It produces no receipt and no number from it is a proving cost. A guest failure on a real `prove` also happens during execution, before any proving work, so negative cases are cheap to confirm with real `prove` too.
- `execute` does not take the lock (it uses little memory). `prove` takes an exclusive `flock` on the file named by `QS_ZK_LOCK` (default `<repo>/.zk_prove.lock`) before proving and holds it until the receipt is written. It refuses to run if `RISC0_DEV_MODE` is set unless `--allow-dev` is passed; with `--allow-dev` the receipt file name must end in `.dev` and stats record `"dev_mode": true`.
- `--po2` sets the segment limit (log2 of cycles per segment). The stats JSON has: `prove_s`, `verify_s`, `cycles`, `user_cycles`, `segments`, `receipt_bytes`, `receipt_kind`, `po2`, `peak_rss_kb` (from `/proc/self/status` VmHWM), `dev_mode`, `image_id`.
- `verify` checks the receipt against the embedded image ID, then compares the journal with the bytes in `pub.bin` (146 bytes, §3).

Exit codes (all subcommands): `0` ok; `2` bad arguments or malformed input file; `3` guest failed, so the relation is false (message `guest-failed` plus the guest's panic text); `4` receipt does not verify (bad seal, wrong image ID, undecodable); `5` receipt verifies but the journal differs from `pub.bin`; `6` lock or dev-mode refusal (`prove` and `verify` both refuse `RISC0_DEV_MODE`; `verify` always, since dev mode accepts fake receipts).

## 10. Locks and builds
- Proving, and any test that proves, runs under the prove lock (taken inside `qs-zk prove`; other tools use `flock -x .zk_prove.lock <cmd>`). Never run two provers at once: the machine has 7.5 GB RAM.
- Cargo builds use one target directory `zk/target` for the workspace. Builds of the guest take minutes; run at most one `cargo build` for `zk/` at a time (`flock -x .zk_build.lock cargo build ...`).
- Dev mode (`RISC0_DEV_MODE=1`) is for fast tests only; those tests carry the pytest marker `dev_mode` or the Rust attribute name suffix `_dev_mode`. No number in any report comes from dev mode.

## 11. Layout
| Path | Owner |
|---|---|
| `zk/Cargo.toml`, `zk/methods/` (embeds the guest ELF and image ID) | lead |
| `zk/guest/` | Agent A |
| `zk/host/` | Agent B |
| `zk/bridge/`, `fl/zk_reference.py` | Agent C |
| `tests/zk/`, `experiments/zk/` | Agent D |
| `zk/probe/` (cost probe, throwaway) | lead |
| `docs/zk_interface.md`, `docs/zk_cost.md`, `docs/decisions.md`, `pq/`, `fl/simulate.py`, `configs/` | lead |

## Change log
- v1 (this file): initial contract.
- v1.4: `verify` refuses RISC0_DEV_MODE (exit 6); ZkPolicy refuses mode `none` and relation != 1 unless `allow_cut`, can pin registered roots, and replay checks run before the proof check (review findings).
- v1.3: clarified opening size (512 bytes), relation 2 has no `n_open` field, and the guest must reject relation 2 with K != 0 or batch != 0. (Agent C found these ambiguous.)
- v1.2: added `execute` subcommand. Paths: workspace `zk/Cargo.toml` (members `host`, `methods`), guest package `qs_guest` in `zk/guest` (own workspace), constants `methods::QS_GUEST_ELF` / `QS_GUEST_ID`. Size at that time K=2, batch=4, po2=18; final size K=4, batch=8 (D-019); the code must work for any K, batch (power of two).
- v1.1: input transport changed from `write_frame` to length + `write_slice` (frame API is unstable in 3.0.6). Blob layout unchanged.
