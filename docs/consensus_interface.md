# Consensus-lite interface (MVP Phase 4)

Scope: `plan/MVP_Phase_4_Consensus_Lite_and_Integration.md`. In scope: n = 4 aggregators, f = 1, quorum 2f+1 = 3, a fixed leader (node 0), synchronous rounds on a simulated asyncio network. Out of scope (deferred, D-020): view change, leader rotation, partial synchrony, real networking, a certificate ledger, n > 4.

## Fault model
- n >= 3f+1 (enforced in `Node.__init__`). Up to f aggregators may be silent or equivocate (`consensus/fault.py`). Clients may be Byzantine.
- A fault only changes what a node sends; honest nodes count votes the same way regardless.
- With 2 faulty nodes the bound is exceeded and a round must not finalize (test).

## Round state machine (per node)
1. **propose**: leader broadcasts `Propose(round, leader_id, W_t)` signed under `QSFL-propose-v1`. A node accepts it once per round (duplicates ignored) after `verify_propose`.
2. **update**: each client sends `Update(client_id, envelope, delta, proof)` to every aggregator. `envelope` is the Phase 2 signed envelope (`QSFL-env-v1`; v2 carries `proof_hash`).
3. **filter**: the node's `verify_update(update) -> (ok, reason)` hook runs. Accepted updates are kept by client id; rejects are logged `(round, client_id, reason)`. Nothing in the aggregate may come from an update that failed the hook.
4. **close**: no more updates for the round (`Close(round)`, a local control message; this is the synchrony assumption).
5. **aggregate**: deterministic. Ids sorted ascending, `DEFENCES[defence]([delta_c...], B2)` in int64 fixed point (`fl/fixedpoint.py`), `W_{t+1} = check(W_t + agg)`, `h_next = SHA256(W_{t+1})`. Same inputs give the same hash at every honest node. No floats, no randomness.
6. **vote**: node signs a vote under `QSFL-vote-v1` over `(round, agg_id, h_next, SHA256("QSFL-set" || sorted accepted ids), nonce)` and broadcasts it.
7. **finalize**: a node finalizes when it holds valid votes from >= 2f+1 distinct aggregators (its own included) for its own `h_next`. First vote per aggregator wins; a second, different vote marks the sender an equivocator and is not counted.

## Messages and domain tags
| message | tag | signed over |
|---|---|---|
| Propose | `QSFL-propose-v1` | alg, round, leader id, H(W_t) |
| Update (envelope) | `QSFL-env-v1` | round, client id, H(W_t), C_i, R_i, nonce [, proof_hash] |
| Vote | `QSFL-vote-v1` | round, agg id, H(W_{t+1}), accepted-set hash, nonce |

Every message is signed under the active scheme set (Ed25519, ML-DSA-65, or hybrid); a missing or extra scheme is rejected (`unsigned` / `scheme_downgrade`).

## verify_update hook contract
- `signature_check(verifier)`: Phase 2 path (signature, round, commitment, nonce).
- `zk_check(...)` (new, Phase 4): signature path plus ZK receipt via `Verifier(zk=ZkPolicy)`; needs `Update.proof` (the receipt bytes).
- Return `(True, "ok")` or `(False, reason)`. Reason codes pass through unchanged: `bad_signature`, `wrong_round`, `replayed_nonce`, `commitment_mismatch`, `bad_proof:{missing_receipt,missing_proof_hash,hash_mismatch,journal_mismatch,unregistered_root,...}`, `scheme_downgrade`, `unsigned`, `no_proposal`.
- A rejected update never burns a nonce and never enters `accepted`.

## Exit properties tested
Benign finalizes every round; each attack is dropped with its reason; one silent node still finalizes; one equivocating node is outvoted; two faulty nodes do not finalize.

## Honest limits
Fixed leader: a silent leader stalls the round (no view change). Synchronous `Close`. Simulated network. Votes finalize an aggregation result, but there is no persisted certificate or chain.
