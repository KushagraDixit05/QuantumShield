# ZK Statement (frozen, Phase 0)

Status: frozen for the MVP. Changes require a new entry in `decisions.md`.

This is the **target relation**. The Phase 3 implementation proves as much of it as fits the machine (7.5 GB RAM). The cut ladder (`plan/99_MVP_Risks_and_Cuts.md`) allows dropping clause (c) to leave (a)+(b). Whatever is actually proven must be stated in the Phase 3 report; nothing outside the implemented clauses may be claimed.

## 1. Fixed-point semantics (shared by FL code and guest)
- All weights, updates and inputs are signed integers with `SCALE = 2^16` (value `v` is stored as `round(v * 2^16)`).
- Weights/updates/activations/gradients: `int64`. Products of two fixed-point values are computed exactly in `int64`, summed, then rescaled with an arithmetic right shift by 16 (floor toward -inf). Every shift is floor. No floats anywhere in the relation.
- Overflow is part of the relation: any intermediate with magnitude >= 2^62 makes the statement false (the prover cannot satisfy it).
- Inputs: sklearn digits pixel `p in 0..16` is stored as `p << 12` (exact).
- Model: MLP 64 -> 32 -> 10, ReLU hidden, linear output, parameter vector `W` of 2,410 `int64` in order `W1 (32x64, row-major), b1 (32), W2 (10x32, row-major), b2 (10)`.
- Loss gradient: one-hot MSE, `dout = out - (onehot << 16)`. Mini-batch gradient is the sum over the batch shifted right by `log2(batch)`; update `W <- W - ((lr_fx * g) >> 16)`.
- Sample selection: step `s`, slot `j` of client `c` in round `t` uses index `u64_le(SHA256("QSFL-idx" || seed || t || c || s || j)[0:8]) mod n_c` (all counters u32 little-endian, `seed` u64 LE).

## 2. Public inputs
| Name | Meaning |
|---|---|
| `t` | round number |
| `H(W_t)` | SHA-256 of the global model vector (little-endian int64) the update starts from |
| `C` | update commitment `SHA256("QSFL-upd" || Δ_le || nonce)` |
| `R` | Merkle root (SHA-256, domain-separated leaf/node) over the client's `n_c` samples `(x, y)` |
| `n_c, seed, c` | dataset size, public sampling seed, client id |
| `K, lr_fx, batch` | local SGD steps, learning rate, batch size |
| `B2` | norm bound, `B^2` in fixed-point units (`2^32` scale) |

## 3. Private witness
`Δ` (2,410 int64), `nonce` (32 bytes), `W_t` (the global model, which the prover also needs to recompute), the sampled `(x, y)` records, and their Merkle paths to `R`.

## 4. Relation
Accept iff all hold:
- (a) **Opening:** `SHA256("QSFL-upd" || Δ || nonce) == C`.
- (b) **Norm bound:** `sum_i Δ_i^2 <= B2`, computed exactly with no overflow.
- (c) **Local training consistency:** `SHA256(W_t) == H(W_t)`; for each of the `K` steps and `batch` slots the sample index follows the sampling rule above; every sampled record has a valid Merkle path to `R`; running the `K` fixed-point SGD steps from `W_t` on those samples gives `W_K` with `W_K - W_t == Δ` exactly.

## 5. What is NOT proven
- **Honesty of data.** The proof binds to whatever is under `R`. A client who committed to flipped labels, or to a poisoned dataset, produces a valid proof. Label-flipping inside the norm bound is **not caught** by this relation.
- **That `R` is the client's genuine dataset.** There is no enrolment or attestation of `R` in the MVP. A client may commit to an adversarially chosen dataset.
- **Any property of the dataset itself** (class balance, outliers, backdoor triggers) beyond the sampled records.
- **Replay and round binding.** The circuit binds `t`, `C`, `H(W_t)` as public inputs, but rejecting a resubmitted proof is the job of the PQ-signed envelope and the aggregators' per-round nonce tracking (Phase 2/4), not of the circuit.
- **Privacy of Δ.** Δ is sent to the aggregators in the clear in the MVP. The proof hides data and nonce (zero-knowledge about the witness), not Δ.
- **Selection bias.** Choosing `seed` publicly prevents the client cherry-picking samples within the proved K steps, but not which data it committed to.
- **Collusion, a compromised aggregator majority, non-IID drift, adaptive in-bound attacks** (e.g. small sign-flipped or slow-poisoning updates that stay under `B`).
- **Quantum security of the ZK system beyond its hash-based assumptions**, and security of anything other than the primitives actually implemented.

## 6. Threat model (5 bullets)
1. Poisoning client: sends an update outside the norm bound, or inconsistent with its committed data.
2. In-bound poisoning client: sends an update within `B`, or trained on bad labels. Out of scope for detection; effect bounded by `B` only.
3. Forged or tampered envelope: stopped by ML-DSA signature verification (Phase 2).
4. Replay of an old envelope/proof: stopped by round-bound, nonce-tracked envelopes (Phase 2/4).
5. One faulty aggregator out of four (f=1) and a quantum adversary against classical signatures (motivates ML-DSA).

## 7. Signed envelope fields (for Phase 2)
`version, round, client_id, C, proof_hash, nonce`.
