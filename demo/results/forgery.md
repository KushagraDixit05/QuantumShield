# Forgery demonstration

**SIMULATION: the adversary is handed the victim's Ed25519 secret key; no quantum computer is used.**

Victim: client 0. Forged update = victim's honest round-0 update x50 (||Δ|| 0.952 -> 47.608; norm bound B = 1.5963). PQ scheme: ML-DSA-65.

## A. One round, real aggregator path (Verifier.verify_envelope)

| mode | honest update (control) | forged: Ed25519 + junk PQ sig | forged: Ed25519 only (downgrade) |
|---|---|---|---|
| classical | accepted (ok) | ACCEPTED (ok) | ACCEPTED (ok) |
| pq | accepted (ok) | rejected (bad_signature) | rejected (scheme_downgrade) |
| hybrid | accepted (ok) | rejected (bad_signature) | rejected (scheme_downgrade) |

## B. Forgery injected every round into FL (FedAvg, no norm filter), seeds [0, 1, 2, 3, 4]

Reference, no forgery and no signatures: final accuracy 0.9421 ± 0.0145. A diverged run (int64 range exceeded, D-012) is scored 0.0.

| signatures | final accuracy (mean ± std) | forged updates dropped / injected |
|---|---|---|
| none | 0.9421 ± 0.0145 | 0 / 0 |
| classical | 0.0000 ± 0.0000 | 0 / 50 |
| pq | 0.9409 ± 0.0161 | 50 / 50 |
| hybrid | 0.9409 ± 0.0161 | 50 / 50 |

Reading: under `classical` the forged update carries a valid Ed25519 signature, so the aggregator cannot tell it from the victim's and FedAvg is destroyed; under `pq` and `hybrid` the missing/invalid ML-DSA signature gets it dropped before aggregation. `none` has no check at all (the injection is not applied because there is no envelope to forge).

Limits: the forged update here is scaled x50, which the Phase 1 norm filter would also catch; the demonstration isolates the signature layer by using plain FedAvg. Signatures prove who sent an update, not that it is good: a client signing its own poisoned update with its own valid key is accepted under every mode.
