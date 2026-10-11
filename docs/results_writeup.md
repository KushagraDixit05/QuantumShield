# Results write-up (one page)

Claim (`plan/00_MVP_Overview.md`): updates carry a PQ signature and a ZK proof; nodes accept only if both verify and finalize with a 2f+1 PQ-signed vote; a poisoning client is rejected and benign accuracy is preserved. Setup: sklearn digits, 64-32-10 integer MLP (2,410 params), 5 clients (1 attacker, client 4), 10 rounds, K=20, batch 32, 5 seeds (0-4), 359 test samples, 4 simulated nodes (f=1). Limits are in `docs/limitations.md`.

## Claims and evidence

| # | Claim | Evidence | Reading |
|---|---|---|---|
| 1 | Benign accuracy is preserved by the defence | `demo/results/scenarios_summary.md`, `scenarios.csv`: none/off 0.9421 +/- 0.0145, none/on 0.9421 +/- 0.0145 | Identical. Same value as the Phase 1 FedAvg baseline (`docs/phase_1_report.md`). |
| 2 | A scaled x50 poisoner destroys plain FedAvg | same files: scaled/off 0.0000 (all 5 seeds diverged; `diverged_round` 4-6 in `scenarios.csv`) | 0.0 is the divergence convention (D-012), not a measured accuracy. |
| 3 | With the defence the scaled poisoner is rejected and accuracy recovers | scaled/on 0.9376 +/- 0.0165; `rejections.csv`: 50 `norm_bound_exceeded` rows, all client 4 | Within 0.5 pt of the benign mean; at 359 test samples this is within noise. The gate here is plaintext, not ZK (limitation 4). |
| 4 | A forged classical signature is accepted classically and rejected with PQ | forged/off 0.0000, forged/on 0.9409 +/- 0.0161; `rejections.csv`: 50 `bad_signature`; `forgery.md` table A: classical ACCEPTED, pq and hybrid rejected (`bad_signature`, `scheme_downgrade`) | The adversary is given the Ed25519 key (simulation). |
| 5 | Replay does not hurt in either mode | replay off/on both 0.9370 +/- 0.0158; `rejections.csv`: `wrong_round` 40 and `stale_key` 5 per mode | Signatures bind the round, so off and on are identical. This is not a defence advantage. |
| 6 | Real proofs verify at every node and gate the vote | `zk_consensus.csv`: rounds 0 and 1 admit clients [0, 1] with 8 real receipt verifications each, attacker refused with `bad_proof:missing_proof_hash`, `finalized_at_nodes`=4; `phase3_fl.csv`: attacker `guest_can_prove=False`, `model_hash_equal_to_non_zk=True` | K=4, batch 8 config; 2 rounds x 2 clients only. Accuracy in that file (0.3008, 0.4123) is from the small config and is not comparable to claims 1-5. |
| 7 | The costs | `overheads.md` | See table below. |

## Costs (all values from `demo/results/overheads.md`)
- Signature bytes per update: Ed25519 94, ML-DSA-65 3343, hybrid 3436.
- Receipt: 3,058,804 B (composite, K=4 batch 8). Prove time 397.7 s per update (range 393.4-402.0; 380-610 in the FL integration runs). Verify 230 ms per proof, CLI including process start.
- Per-round consensus latency (compute only, simulated network): 5.4 ms defence off, 7.8 ms defence on, 1615.3 ms with real receipt verification (4 nodes, 8 receipts per round, excluding proving).
- Bandwidth per update: envelope 232 B off vs 3574 B on; envelope + delta + receipt 3,081,658 B vs 19,512 B.

## Figures
`demo/results/accuracy.png` (accuracy vs round for benign, poisoned without defence, poisoned with defence) and `demo/results/attack_matrix.png` (attack outcomes).

## What this does not show
Accuracy and ZK evidence come from different configurations (plaintext gate for 50 updates per run; 4 real proofs at K=4). Label-flip, in-bound sign-flip and slow poisoning are not stopped by the norm clause (Phase 1 report: label-flip and sign-flip x1 are accepted by the norm filter, with drops of 1.67 and 3.45 points under FedAvg). Delta is visible to aggregators. Proving every update in a round is not interactive.
