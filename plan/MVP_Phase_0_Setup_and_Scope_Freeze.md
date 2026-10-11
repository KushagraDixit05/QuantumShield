# MVP Phase 0 — Setup & Scope Freeze (1–2 days)

## Goal
A working environment and a frozen, written MVP scope so later phases don't drift.

## Tasks
- [ ] Create repo `quantumshield-fl/` with the layout in `00_MVP_Overview.md`; `git init`; venv; `requirements.txt`
- [ ] Install and smoke-test `liboqs-python` (sign/verify one message with ML-DSA-65). If the build fails within 2 hours, switch to `dilithium-py` and note it
- [ ] Install ZK toolchain (Rust + RISC Zero `rzup`) and run its hello-world prove/verify. If it fails within half a day, plan on `mock` backend + attempt later (see Risks)
- [ ] Freeze parameters in `config.py`: n=4 aggregators, f=1, 5 clients (1 malicious), rounds=10, model 784→32→10 (or sklearn digits 64→32→10), fixed-point scale 2^16, norm bound B
- [ ] Write `docs/mvp_statement.md`: public inputs (round, C_i, B), private witness (Δ_i, nonce), checks (opening, norm bound); threat model in 5 bullets (poisoning client, forged signature, replay, one faulty aggregator, quantum adversary on classical signatures)
- [ ] Define the signed envelope fields: version, round, client_id, C_i, proof hash, nonce

## Files created
`config.py`, `requirements.txt`, `docs/mvp_statement.md`, empty module folders, `tests/test_smoke.py`

## Exit criteria
- [ ] ML-DSA sign/verify smoke test passes
- [ ] ZK toolchain hello-world runs, or the fallback decision is written down
- [ ] `docs/mvp_statement.md` committed and frozen

## Deferred
CI, Docker, experiment tracking.
