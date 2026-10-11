# Phase 4 report: Consensus-lite and integration (MVP plan numbering)

Scope follows `plan/MVP_Phase_4_Consensus_Lite_and_Integration.md` (D-020). The brief's view change, leader rotation, partial synchrony, n = 7/10/16, network simulator and certificate ledger are **not built** (see `docs/deferred.md`).

## What was built
| item | path | by |
|---|---|---|
| Interface contract (fault model, round state machine, tags, hook contract) | `docs/consensus_interface.md` | lead |
| `zk_check(verifier)` hook, `Node.drop_log()`, `accepted_ids(rnd)`, `votes_by_hash(rnd)`; 4 stubbed tests | `consensus/node.py`, `tests/test_consensus.py` | Agent E |
| Swapped-proof attack, `ATTACKS` table (scaled, forged, replay, swap); 12 tests, 2 with the real verifier | `attacks/envelope_attacks.py`, `attacks/registry.py`, `tests/test_attacks.py` | Agent F |
| Integration and fault tests (14) | `tests/test_integration.py` | Agent G |
| End-to-end driver | `demo/run_demo.py`, `configs/demo.yaml` | lead |
Existing from earlier phases and reused unchanged: `consensus/messages.py`, `fault.py`, `Node`, `pq/session.py`, `pq/zkpolicy.py`. Status files: `docs/status/p4-{E,F,G}.md`.

## Commands and results
```
$ .venv/bin/python -m pytest -q --ignore=tests/zk     -> 140 passed in 37.02s
$ .venv/bin/python -m pytest -q tests/zk              -> 116 passed in 14.80s   (uses the cached Phase 3 receipt; no proving)
$ .venv/bin/python -m demo.run_demo --all             -> about 21 s wall (via `make demo`, regenerated from scratch) (scenario matrix + real-receipt stage)
```
Tests labelled `# unit test, stubbed verifier, not a proof result` use a stub receipt verifier; they test wiring, not proofs. Real-verifier tests: 2 in `test_attacks.py`, 1 in `test_integration.py`, all verify-only on `demo/results/zk/r0_c0.receipt`. No prover was run in Phase 4 and `RISC0_DEV_MODE` was never set.

Exit criteria (`tests/test_integration.py`, 14 tests, all pass): benign run finalizes every round at every node with identical hashes; each attack dropped with its reason (`bad_proof:missing_proof_hash`, `bad_signature`, `scheme_downgrade`, `wrong_round`, `replayed_nonce`, `bad_proof:journal_mismatch`, `bad_proof:hash_mismatch`) and never in the accepted set; one silent node still finalizes; one equivocating node is outvoted (3 votes vs 1); all three two-fault combinations fail to finalize.

### Real-receipt consensus (`demo/results/zk_consensus.csv`, `zk_config: configs/phase3.yaml`, K=4, batch 8)
Clients 0 and 1 use the real Phase 3 receipts; the client-4 x50 attacker has none. Four nodes each run the real `qs-zk` verify (8 verifications per round; timings vary run to run, values from the final `make demo`).
| round | accepted | finalized at | accuracy | attacker reason | round latency (verify at 4 nodes, no proving) |
|---|---|---|---|---|---|
| 0 | [0, 1] | 4/4 | 0.3008 | bad_proof:missing_proof_hash | 1617 ms |
| 1 | [0, 1] | 4/4 | 0.4123 | bad_proof:missing_proof_hash | 1613 ms |
Accuracies equal the Phase 3 run (`demo/results/phase3_fl.csv`: 0.3008, 0.4123), so the consensus path aggregates the same models.

### Accuracy with the attacker (`demo/results/scenarios.csv`, seeds 0-4, K=20, batch 32, 10 rounds, 359 test samples)
| attack | defence off | defence on |
|---|---|---|
| none | 0.9421 | 0.9421 |
| scaled x50 | 0.0000 (diverged, D-012) | 0.9376 |
| forged (stolen Ed25519 key) | 0.0000 (diverged) | 0.9409 |
| replay | 0.9370 | 0.9370 |
Defence on with the scaled attacker is 0.45 points below the clean run (within the plan's ~2 points; the 359-sample test set makes this suggestive only). Replay is rejected in both modes (`wrong_round`, 5 `stale_key`) because signatures bind the round; its small loss is the missing attacker contribution.

## Hardware
Intel i5-11260H, 12 threads, 7.5 GiB RAM, Linux 7.0.

## Deviations, decisions, open issues
- D-020: MVP scope, not the brief's Phase 4.
- "Defence on" in the scenario matrix = hybrid Ed25519 + ML-DSA-65 + a **plaintext norm gate** (`norm_bound_exceeded`), not a ZK proof, for the ~50 updates per run. Real ZK evidence is the 2-round K=4 stage above only (4 real proofs from Phase 3). The two stages use different K/batch/B, so they are not one experiment.
- "Defence off" = classical Ed25519 only + plain FedAvg.
- Fixed leader: a silent leader stalls the round (no view change). Quorum counting uses synchronous `Close`.
- Latency is in-process compute time, not network time.
- `forged` and `scaled` under defence off diverge the int64 model; accuracy 0.0 is the D-012 convention.
- Open: no persisted certificate/ledger; Phase 3 receipts are the only real proofs, so integration with a freshly proved update would take ~6-10 min per update.
