# 5-minute demo script

This is the script for the user to record. The assistant cannot make the screen recording. Read it aloud while running the commands in a terminal at the repo root with the venv set up (`make setup`). Times are approximate. `make demo` takes a few minutes in total; start it before recording, or cut the wait.

## 0:00 Claim (30 s)
Show `README.md` top. Say: every update carries a post-quantum signature and a ZK proof; nodes accept only if both verify and finalize with 2f+1 PQ-signed votes; a poisoning client is rejected while benign accuracy is preserved. This is a small, single-machine, simulated-network demo.

## 0:30 One command (30 s)
```
make demo
```
Point at: the three stages (scenarios, zk, then plot and overheads). Say the ZK stage verifies four stored real RISC Zero receipts and does not run the prover.

## 1:00 Accuracy figure (60 s)
```
xdg-open demo/results/accuracy.png
cat demo/results/scenarios_summary.md
```
Point at: curve A (benign), B (poisoned, plain FedAvg, diverges, scored 0.0 by convention), C (poisoned, QuantumShield on). In the table, the `none` rows are equal for off and on, and `scaled on` is close to `none`. Say: 5 seeds, 359-sample test set, so 1-2 point differences are suggestive only.

## 2:00 Rejections (60 s)
```
head -5 demo/results/rejections.csv
cut -d, -f1,2,6 demo/results/rejections.csv | sort | uniq -c
```
Point at: `norm_bound_exceeded` for the scaled attacker (client 4), `bad_signature` for the forged update. Note replay is rejected in both modes (`wrong_round`, `stale_key`) because signatures bind the round.

## 3:00 Forgery (45 s)
```
cat demo/results/forgery.md
```
Point at table A: classical accepts the forged update, pq and hybrid reject it. Say the adversary was handed the Ed25519 key; no quantum computer is used.

## 3:45 Real proofs and the vote (60 s)
```
cat demo/results/zk_consensus.csv
```
Point at: honest clients 0 and 1 admitted with real receipts verified; the attacker row `admitted=False` with `guest_can_prove=False`; `finalized_at_nodes` = 4; `model_hash_equal_to_non_zk=True`. Say these proofs are K=4, batch 8, not the K=20, batch 32 of the accuracy runs.

## 4:45 Overheads and honesty (15 s)
```
cat demo/results/overheads.md
```
Point at the signature, proof and latency rows. Close on `docs/limitations.md`: Delta is visible to aggregators; the accuracy runs use a plaintext norm gate; label-flip inside the bound passes; n=4 simulated.
