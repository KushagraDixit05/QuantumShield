# ZK proving benchmark (real RISC Zero proofs, no dev mode)

- Hardware: 11th Gen Intel(R) Core(TM) i5-11260H @ 2.60GHz, 12 logical CPUs, 7.5 GiB RAM
- Guest image id: `c66b4507dff763d1eec563ee5db435490b15ac98bb962cb1c973e498c5360a10`
- Config: K=4, batch=8, po2=18, relation=1
- Runs: 2 (composite); run i proves a distinct honest vector

| run | vector | kind | prove_s | verify_s | agg_check_s | receipt_bytes | cycles | user_cycles | segments | peak_rss_MB |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | honest_main_s0_t0_c0 | composite | 402.0 | 0.238 | 0.197 | 3058804 | 3014656 | 2127722 | 12 | 2364 |
| 1 | honest_main_s0_t0_c1 | composite | 393.39 | 0.222 | 0.201 | 3058804 | 3014656 | 2134158 | 12 | 2366 |

| metric | median | min | max |
|---|---|---|---|
| prove_s | 397.695 | 393.39 | 402.0 |
| verify_s | 0.22999999999999998 | 0.222 | 0.238 |
| agg_check_s | 0.199 | 0.197 | 0.201 |
| receipt_bytes | 3058804.0 | 3058804 | 3058804 |
| cycles | 3014656.0 | 3014656 | 3014656 |
| user_cycles | 2130940.0 | 2127722 | 2134158 |
| segments | 12.0 | 12 | 12 |
| peak_rss_kb | 2422680.0 | 2421732 | 2423628 |

verify_s = wall clock of one `qs-zk verify` call (includes process start). agg_check_s = `Session.admit` with a hybrid-signed v2 envelope (signatures + commitment + proof_hash + real verify).
