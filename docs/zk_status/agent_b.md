# Agent B status (zk/host, `qs-zk`)

## Done
- `qs-zk` with `image-id`, `prove`, `verify`, `execute` per docs/zk_interface.md section 9. Exit codes 0/2/3/4/5/6 implemented.
- `prove`: validates args and input (magic QSZK, >= 178 bytes) -> dev-mode check (exit 6) -> takes flock on `QS_ZK_LOCK` (default `<repo>/.zk_prove.lock`, held until receipt, journal and stats are written) -> runs the executor first (any execution failure = exit 3 `guest-failed: <text>`, costs seconds) -> `prove_with_opts` -> verifies the receipt against QS_GUEST_ID -> writes bincode receipt, 146-byte journal, stats JSON (also on stdout). A prover error whose text names a guest panic is also exit 3; other prover errors exit 1.
- Dev mode: the env var being set at all makes `prove` exit 6 unless `--allow-dev`; with it the receipt name must end `.dev` (else exit 2) and stats say `dev_mode: true`. The variable name appears only in main.rs (read via `var_os`, the guard); test file only sets it on a child process via `.env(...)`, which the repo's grep test (assignment patterns only) accepts.
- Peak memory: `peak_rss_kb` = max of (a) a poller thread reading `/proc/<pid>/status` VmHWM of direct children of the host (r0vm) every 200 ms and (b) `getrusage(RUSAGE_CHILDREN).ru_maxrss` after the prove. The source is stated in the stats (`peak_rss_source`). `host_rss_kb` is the host's own VmHWM.
- Extra flags: `--po2` (13..24, default 18), `--kind composite|succinct`, `--allow-dev`, `verify --journal-out`, `execute --po2`. Stats also carry a `mode` field. `execute` stats: execute_s, cycles (sum of 2^po2 over segments), user_cycles, segments, po2, image_id.

## Files
- /media/kushagra/crucial/QuantumShield/zk/host/Cargo.toml (adds `libc`, already in Cargo.lock)
- /media/kushagra/crucial/QuantumShield/zk/host/src/main.rs
- /media/kushagra/crucial/QuantumShield/zk/host/tests/cli.rs

## Real test output (`cargo test --release -p qs-zk`, no proving)
```
test image_id_is_64_hex ... ok
test allow_dev_needs_dev_suffix_dev_mode ... ok
test prove_refuses_dev_mode ... ok
test verify_garbage_receipt_is_4 ... ok
test args_unknown_subcommand_is_2 ... ok
test truncated_or_bad_magic_input_is_2 ... ok
test args_missing_and_bad_flags_are_2 ... ok
test execute_relation2_journal_matches_input ... ok
test execute_tampered_input_is_3 ... ok
test execute_relation1_k2_batch4_journal_matches_input ... ok
test result: ok. 10 passed; 0 failed
```
Execute smoke (guest as built at the time of the run, image id 32188f79...17f9): K=2 batch=4 relation 1: user_cycles 2,140,066, cycles 2,899,968, 12 segments, 0.09 s, journal == first 146 bytes of input. Relation 2: user_cycles 326,959, cycles 524,288, 2 segments, journal equal. A bit flip in C makes `execute` exit 3 with `guest-failed`. (Note: cycle counts equal the probe's run B exactly, so the guest in zk/guest may still be the probe-equivalent at that moment.)

## Blocked
- The ONE smoke `prove` (K=1 batch=1 relation 2) has NOT been run: docs/zk_status/agent_a.md does not exist yet, so Agent A has not reported the guest as built. Run once A reports: `.venv/bin/python zk/probe/make_input.py $S/in.bin 1 1 2 && zk/target/release/qs-zk prove --input $S/in.bin --receipt $S/r.bin --journal $S/j.bin --stats $S/s.json` (then `qs-zk verify --receipt ... --expect <first 146 bytes>`).
- The `verify` happy path (exit 0 and exit 5) is untested until a receipt exists.

## Needs from others
- Agent A: report in docs/zk_status/agent_a.md when the guest is final (the tests' image id and cycle numbers will change then; tests do not hard-code them).
