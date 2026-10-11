# Overheads

Hardware: 11th Gen Intel(R) Core(TM) i5-11260H @ 2.60GHz, 12 threads, 7.5 GiB RAM, Linux 7.0.0-34-generic, Python 3.11.17, liboqs 0.16.0, liboqs-python 0.16.0.1, cryptography 50.0.2, single process, sequential

Signature bytes and sign/verify times were measured now with 20 repetitions. Payload-only baseline = 138 B (update envelope, no signature). Every ZK row is read from the existing real-proof files named in the last column; the prover was not run here and RISC0_DEV_MODE is not used.

Notes:
- The network is simulated in-process, so the latency rows are compute time, not network time.
- Prove time per update is about 6-10 minutes (about 6.5 min on a quiet machine, up to about 10 min under load), so proving every update in a round is not interactive.
- Prove time varies by about 1.6x run-to-run on this machine; treat it as a range.
- Without QuantumShield = the Ed25519-signed baseline (defence off in scenarios.csv); the proof columns have no baseline cost.

| metric | with QuantumShield | without | source |
|---|---|---|---|
| signature bytes / update, Ed25519 only | 94 | n/a (this is the classical baseline) | measured now |
| signature bytes / update, ML-DSA-65 | 3343 | 94 (Ed25519) | measured now |
| signature bytes / update, hybrid Ed25519 + ML-DSA-65 | 3436 | 94 (Ed25519) | measured now |
| sign time (ms, median): Ed25519 / ML-DSA-65 / hybrid (sum) | 0.059 / 0.087 / 0.146 | 0.059 (Ed25519) | measured now |
| verify time (ms, median): Ed25519 / ML-DSA-65 / hybrid (sum) | 0.098 / 0.029 / 0.127 | 0.098 (Ed25519) | measured now |
| proof size (bytes, composite receipt, K=4 batch 8) | 3,058,804 | 0 (no proof) | zk_bench.csv, median of 2 real proofs |
| prove time (s / update) | 397.7 (range 393.4-402.0; FL integration runs 380-610, about 1.6x run-to-run variability) | 0 | zk_bench.csv (2 runs); phase3_fl.csv (4 proofs) |
| verify time (ms / proof, qs-zk CLI incl. process start) | 230 | 0 | zk_bench.csv |
| per-round consensus latency (ms), signatures + defence | 6.7 | 4.7 | scenarios.csv, mean_round_latency_ms over 20 defence-off / 20 defence-on runs |
| per-round consensus latency (ms), with real receipt verification (4 nodes, 8 receipts/round) | 1470.6 | 4.7 | zk_consensus.csv, mean of 2 rounds; excludes proving |
| bandwidth / update (bytes): envelope | 3574 | 232 | scenarios.csv mean_update_env_bytes (defence on / off) |
| bandwidth / update (bytes): envelope + delta vector | 22,854 | 19,512 | delta = 2410 x 8 = 19,280 B |
| bandwidth / update (bytes): envelope + delta + receipt | 3,081,658 | 19,512 | receipt bytes from zk_bench.csv |
