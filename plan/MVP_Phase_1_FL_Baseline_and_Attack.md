# MVP Phase 1 — FL Baseline & Attack (3–4 days)

## Goal
A minimal federated-learning loop plus one attack that visibly breaks it. This is the "problem" half of the demo.

## Tasks
- [ ] `fl/data.py`: load MNIST (or sklearn digits for zero download), IID-split across 5 clients, shared test set
- [ ] `fl/model.py`: tiny MLP, flatten/unflatten parameters to a single vector
- [ ] `fl/client.py`: `local_train(W_t) -> Δ_i` (1–2 epochs SGD)
- [ ] `fl/aggregate.py`: FedAvg; coordinate-wise median or norm-clipped mean as the "robust" option used later
- [ ] `fl/simulate.py`: run R rounds, log test accuracy per round to CSV
- [ ] `attacks/poison.py`: malicious client sends `Δ * s` (scale, e.g. s=50) or large Gaussian noise
- [ ] Record: clean-baseline accuracy, accuracy under attack with plain FedAvg

## Tests
- Parameter flatten/unflatten round-trips
- Clean FedAvg reaches expected accuracy (≥ ~90% on MNIST MLP, or the digits equivalent)
- Attack run is clearly worse than clean run

## Exit criteria
- [ ] `python -m fl.simulate --attack none|scaled` produces two accuracy curves
- [ ] Baseline numbers written to `demo/results/baseline.csv`
- [ ] Norm bound B chosen from benign update norms (e.g. 99th percentile × margin) and saved to config

## Deferred
Non-IID splits, other datasets, other attacks.
