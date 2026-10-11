# Limitations: what this MVP does not prove

Each item is a constraint on the claim in `plan/00_MVP_Overview.md`.

## Privacy
1. **Delta is visible to aggregators.** The proof shows properties of Delta; it does not hide it. There is no secure aggregation and no differential privacy. The ZK is used for integrity, not confidentiality.

## What the ZK relation covers
2. **Reduced size.** The relation (commitment opens to Delta, ||Delta||^2 <= B^2, Delta equals K fixed-point SGD steps on Merkle-opened samples) is proved only at **K=4, batch 8**. It was cut from K=20, batch 32 because that is about 4.5 h per proof with the probe guest and untested with the production guest (D-017, D-019). Benign accuracy at K=4, batch 8 is about 0.76 after 10 rounds on the calibration seed (D-019), versus 0.94 at K=20, batch 32.
3. **Only 4 real proofs exist** (Phase 3: rounds 0 and 1 x clients 0 and 1, K=4). The consensus + ZK check (`demo/results/zk_consensus.csv`) uses exactly these receipts; nothing was proved during `make demo`.
4. **ZK evidence and accuracy evidence come from different configurations.** The scenario runs (K=20, batch 32, 10 rounds, 5 clients, 50 updates per run) use a **plaintext norm gate** (`||Delta||^2 <= B^2`) in place of ZK, because proving 50 updates would take about 5 hours. The gate is the policy the proof enforces, but those accuracy numbers are not ZK results. Nothing here shows end-to-end accuracy with real proofs at K=20.
5. **The committed dataset is not attested.** The Merkle root R is chosen by the client unless registered roots are configured on the aggregator. A client can commit to poisoned data and prove honest training on it.
6. **Label-flip inside the norm bound is not caught.** The client trains honestly on the data it committed to, so it passes norm and SGD-consistency clauses.
7. **In-bound sign-flip and slow poisoning are not stopped by the norm clause.** An update with benign-sized norm passes. A sign-flipped update would fail the SGD recompute clause only when the client cannot also commit to matching data; a client that commits to adversarial data passes. Small, persistent in-bound drift is out of scope. Phase 1 recorded a paired 3.45 +/- 1.55 point drop for sign-flip x1 under plain FedAvg (`docs/phase_1_report.md`).

## Signatures
8. **Signatures authenticate senders, not updates.** A client signing its own poisoned update with its own valid key is accepted under every mode (`demo/results/forgery.md`).
9. **"Defence off" means classical Ed25519 + plain FedAvg** with no norm gate. It is a specific baseline, not "no security".
10. **Replay is rejected in both modes** (reasons `wrong_round`, `stale_key` in `rejections.csv`), because signatures bind the round. So the replay row is identical for defence off and on and does not demonstrate an advantage of the defence. A stale delta re-signed under a fresh round and nonce is not detected by signatures alone (D-016).
11. The forgery demonstration hands the adversary the victim's Ed25519 key. No quantum computer is used; it models the post-quantum threat.
12. The PKI is simulated (no enrolment, no certificate chain, in-process secret keys, local revocation set). Seeded RNG in `pq/sig.py` is for experiments only (D-015).

## Consensus and network
13. **Simulated asyncio network, fixed leader, no view change, no partial synchrony, n=4 and f=1 only.** Tolerates one silent or faulty node in the tests; says nothing about larger n, leader failure, or adversarial scheduling. Not a production consensus protocol.

## Measurement
14. **Small model** (2,410 parameters, sklearn digits, IID split over 5 clients). Results may not transfer to larger models or non-IID data.
15. **359-sample test set.** One sample is about 0.28 points; with 5 seeds, differences of 1-2 points are suggestive only.
16. **Divergence is recorded as accuracy 0.0 by convention** (D-012): a scaled x50 update under plain FedAvg leaves the int64 range, and the run is scored 0.0 from that round. This is not a measured accuracy. Those "0.0000" cells mean "diverged".
17. The norm bound B is calibrated on benign updates of a separate seed (100) x 1.5 (D-011); evaluation seeds are 0-4. B is tuned for this model and attack.
18. Timings are single-machine, single-threaded Python-wrapper numbers with about 20% run-to-run variation (Phase 2 report). Proving used a laptop CPU (2.4 GB peak RAM).
19. The ZK backend is the real RISC Zero zkVM (no mock, D-002; dev mode refused). It is hash-based and plausibly post-quantum, but this repository does not analyse the concrete security level, and receipts are large (about 3 MB each, composite).
