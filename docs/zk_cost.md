# ZK proving cost measurements (Phase 3, Step 0)

Real proofs only (`RISC0_DEV_MODE` unset, host asserts it). Hardware: Intel i5-11260H @ 2.60 GHz, 12 threads, 7.5 GiB RAM (about 2-3 GiB available during runs: browser and desktop apps were open), Linux 7.0.0-34, CPU proving, risc0-zkvm 3.0.6, release build. Guest: `zk/probe/methods/guest` (docs/zk_interface.md logic, i64 integer only). Input from `zk/probe/make_input.py` (client 0, round 0, seed 0, n_c = 288). Segment limit po2 = 18, composite receipt. Peak memory is the `r0vm` prover child process (`/usr/bin/time -v`, max RSS; the host process itself is about 30 MB).

| run | relation | K | batch | unique records | user cycles | total cycles | segments | prove time | verify | receipt | peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | commitment + norm | - | - | - | 325,115 | 524,288 | 2 | 68.2 s | 29 ms | 512,096 B | 2.42 GB |
| B | full (a)+(b)+(c) | 2 | 4 | 8 | 2,140,066 | 2,899,968 | 12 | 377.1 s | 171 ms | 3,013,492 B | 2.42 GB |
| C | full (a)+(b)+(c) | 1 | 32 | 28 | 5,049,585 | 6,553,600 | 25 | 981.1 s | 516 ms | 6,396,462 B | 2.42 GB |

Failed attempt: run C at po2 = 20 was killed (exit 137, out of memory) with about 3 GB available. po2 = 19 was not tried.

## Reading the numbers
- Proving speed is about 7-8k total cycles/s (about 130-150 us per cycle). Prove time is linear in total cycles; peak RSS is set by po2 (2.42 GB at 18) and did not grow with cycles.
- Fixed cost (hashing W_t twice-sized data, commitment, norm): about 0.33M user cycles.
- SGD cost per step is about 0.45M cycles plus about 0.13M cycles per sample in the batch (fits B and C: step at batch 4 about 0.9M, at batch 32 about 4.6M).
- Extrapolation to the Phase 1 setting K = 20, batch 32: about 95M user cycles, about 125M total, about 4.5 hours per proof. Not provable in the demo.
- Total cycles include padding up to a power-of-two segment, so small runs waste cycles.

## Decision (also in docs/decisions.md D-017)
K = 2, batch = 4, po2 = 18, composite receipt: about 6.3 minutes and 2.4 GB per proof, 3.0 MB receipt. This is the largest setting that keeps a single proof near the 10 minute target; K = 1, batch 32 already takes 16 minutes.

## Production guest (Agent A, `zk/guest`), measured through `qs-zk` (supersedes the decision above)
Agent A's guest runs the same relation in far fewer cycles (executor, user cycles / total cycles):

| input | probe guest | production guest |
|---|---|---|
| relation 2 | 325,115 / 524,288 | 105,247 / 262,144 |
| K=2, batch 4 | 2,140,066 / 2,899,968 | 793,502 / 1,179,648 |
| K=4, batch 4 | - | 1,345,681 / 1,966,080 |
| K=4, batch 8 | - | 2,127,722 / 3,014,656 |
| K=8, batch 4 | - | 2,417,206 / 3,473,408 |
| K=1, batch 32 | 5,049,585 / 6,553,600 | 1,866,553 / 2,490,368 |
| K=4, batch 16 | - | 3,654,494 / 4,980,736 |

Real proof with the production guest via `qs-zk prove` (`/usr/bin/time -v` around it), K=4, batch 8, 31 unique records, po2 18, composite:

| prove | verify | receipt | cycles (total / user) | segments | peak RSS (r0vm child) |
|---|---|---|---|---|---|
| 381.9 s (6 min 22 s) | 0.17 s | 3,058,804 B | 3,014,656 / 2,127,722 | 12 | 2.42 GB |

`qs-zk verify` of that receipt against the true public bytes: exit 0. Against public bytes with one byte changed: exit 5 (receipt verifies, journal differs). Prove speed is again about 7.9k total cycles/s.

Decision: K = 4, batch = 8 (see D-019). The machine had about 3.5 GB available during this run.
