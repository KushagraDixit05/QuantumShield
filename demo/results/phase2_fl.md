PQ scheme for pq/hybrid: ML-DSA-65; seeds [0, 1, 2, 3, 4]; B = 1.5963; final-round accuracy, mean ± std (population std); diverged = int64 range exceeded (scored 0.0, D-012).

| scenario (defence) | none | classical | pq | hybrid |
|---|---|---|---|---|
| benign (fedavg) | 0.9421 ± 0.0145 | 0.9421 ± 0.0145 | 0.9421 ± 0.0145 | 0.9421 ± 0.0145 |
| scaled-x50 (own key) (norm_filter) | 0.9376 ± 0.0165 | 0.9376 ± 0.0165 | 0.9376 ± 0.0165 | 0.9376 ± 0.0165 |
| replay stale delta (own key, re-signed) (fedavg) | 0.9265 ± 0.0189 | 0.9265 ± 0.0189 | 0.9265 ± 0.0189 | 0.9265 ± 0.0189 |
| replay old envelope (fedavg) | n/a (needs signatures) | 0.9370 ± 0.0158; dropped {'wrong_round': 40, 'stale_key': 5} | 0.9370 ± 0.0158; dropped {'wrong_round': 40, 'stale_key': 5} | 0.9370 ± 0.0158; dropped {'wrong_round': 40, 'stale_key': 5} |
| tamper delta (fedavg) | n/a (needs signatures) | 0.9376 ± 0.0165; dropped {'commitment_mismatch': 50} | 0.9376 ± 0.0165; dropped {'commitment_mismatch': 50} | 0.9376 ± 0.0165; dropped {'commitment_mismatch': 50} |

Benign curves identical across all modes for every seed: True

FL loop per PQ algorithm (pq mode, benign, FedAvg, seed 0):

| algorithm | final accuracy | identical to `none` | wall time (s) |
|---|---|---|---|
| ML-DSA-44 | 0.9526 | True | 0.2 |
| ML-DSA-65 | 0.9526 | True | 0.3 |
| Falcon-512 | 0.9526 | True | 0.4 |
| SLH-DSA-128s | 0.9526 | True | 38.4 |
