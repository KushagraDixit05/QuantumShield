# MVP Phase 4 — Consensus-Lite & Integration (3–4 days)

## Goal
Wire FL + PQ signatures + ZK proofs into one verifiable round protocol across 4 simulated aggregator nodes tolerating f=1 faulty node.

## Round protocol
1. Leader broadcasts current model W_t and round number
2. Clients train, commit, prove, sign, and send envelopes to all aggregators
3. Each aggregator: `verify_envelope` (PQ) → `zk.verify` → keep valid updates only (drop and log rejects with reason)
4. Each aggregator computes the robust aggregate and W_{t+1}; signs a vote on H(W_{t+1}) with ML-DSA
5. Votes are broadcast; a node finalizes when it holds 2f+1 = 3 valid votes for the same hash
6. Clients adopt the finalized W_{t+1}

## Tasks
- [ ] `consensus/messages.py`: Propose, Update, Vote types; all signed
- [ ] `consensus/node.py`: aggregator logic above (asyncio queues as the network)
- [ ] `consensus/fault.py`: faulty-node modes — silent, and equivocating (votes on a wrong hash)
- [ ] `attacks/`: scaled update, forged signature, replayed envelope, proof swapped from another client
- [ ] `demo/run_demo.py`: runs R rounds with flags `--defence on|off --attack ...`, logs accepted/rejected per round

## Tests (`tests/test_integration.py`)
- Benign run finalizes every round
- Each attack is rejected with the expected reason code
- One silent node → still finalizes; one equivocating node → its vote is outvoted
- Two faulty nodes → round does not finalize (shows the bound)

## Exit criteria
- [ ] Full round runs end to end with real PQ + ZK (mock ZK only if Phase 3 fallback 3 applied)
- [ ] All attack and fault tests pass
- [ ] Accuracy with defence on and the attacker present is within ~2 pts of clean baseline

## Deferred
Leader rotation / view change, real networking, partial synchrony, Sybil resistance, secure aggregation.
