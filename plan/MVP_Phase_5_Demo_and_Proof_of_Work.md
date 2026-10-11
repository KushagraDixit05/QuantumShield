# MVP Phase 5 — Demo & Proof-of-Work Package (2–3 days)

## Goal
Package evidence that the claim in `00_MVP_Overview.md` holds, reproducibly.

## Tasks
- [ ] Three scenarios, same seed: (A) benign, no attack; (B) poisoned client, plain FedAvg; (C) poisoned client, QuantumShield on
- [ ] `demo/plot.py`: accuracy-vs-round for A/B/C in one figure
- [ ] Overhead table (`demo/results/overheads.md`): signature size, proof size, prove time, verify time, per-round latency, bandwidth per update, with and without QuantumShield
- [ ] Rejection log excerpt showing the attacker's update refused with reason (ZK norm fail), plus a forged-signature rejection
- [ ] One command: `make demo` (or `python -m demo.run_demo --all`) regenerates results and figure
- [ ] README: what it proves, how to run, honest limitations (Δ visible to aggregators; relation is norm+commitment only; simulated network; mock-vs-real ZK status)
- [ ] 5-minute demo script and screen recording
- [ ] One-page results write-up and a "deferred to the full plan" list mapping to `../plan/Phase_*.md`

## Exit criteria
- [ ] A fresh clone reproduces figure and tables with one command
- [ ] Benign accuracy within ~2 pts of baseline; poisoned-with-defence recovers to near baseline
- [ ] Limitations section is explicit about what is not proven

## Next step after MVP
Extend toward the full plan: SGD-step recomputation (Phase 4 Step 4.4), non-IID data and more attacks (Phase 6), scaling benchmarks (Phase 7), paper (Phase 8).
