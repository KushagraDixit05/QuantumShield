# p5-I status (overheads)

Done: demo/overheads.py rewritten (reads zk_bench.csv, phase3_fl.csv, scenarios.csv, zk_consensus.csv; --zk-json kept as optional override; --results DIR). tests/test_overheads.py created (3 tests pass). demo/results/overheads.md regenerated, no 'pending' cells, includes hardware line and the simulated-network / not-interactive notes.
Blocked: nothing. Needs: nothing.
Commands: `.venv/bin/python -m demo.overheads` (ok); `.venv/bin/python -m pytest tests/test_overheads.py -q` -> 3 passed.
Notes: "without" = Ed25519-signed baseline (scenarios defence off, 232 B envelope). Prover never run.
