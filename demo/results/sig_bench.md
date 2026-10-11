Hardware/software: 11th Gen Intel(R) Core(TM) i5-11260H @ 2.60GHz, 12 threads, 7.5 GiB RAM, Linux 7.0.0-34-generic, Python 3.11.17, liboqs 0.16.0, liboqs-python 0.16.0.1, cryptography 50.0.2, single process, sequential

Reps: {'keygen': 50, 'sign': 300, 'sign_slow': 20, 'verify': 500}; message 150 B; system RNG; times are medians (ms), p95 in brackets.

| algorithm | pk (B) | sig (B) | keygen ms | sign ms | verify ms |
|---|---|---|---|---|---|
| Ed25519 | 32 | 64 | 0.032 (0.038) | 0.058 (0.063) | 0.088 (0.094) |
| ML-DSA-44 | 1312 | 2420 | 0.032 (0.049) | 0.056 (0.131) | 0.020 (0.020) |
| ML-DSA-65 | 1952 | 3309 | 0.038 (0.042) | 0.071 (0.171) | 0.027 (0.030) |
| Falcon-512 | 897 | 656 | 4.851 (7.217) | 0.202 (0.209) | 0.037 (0.041) |
| SLH-DSA-128s | 32 | 7856 | 53.2 (60.0) | 450.4 (479.8) | 0.474 (0.568) |

Falcon-512 signatures are variable length (reported = the sample observed; max 752 B).

Bytes added by the signature layer (real wire encoding: signature(s), key ids, algorithm labels) per update envelope and per vote; the update itself is 19280 B (2,410 int64):

| config | per update envelope (B) | % of update | per vote (B) | per round, 5 clients + 4 votes (B) |
|---|---|---|---|---|
| Ed25519 | 94 | 0.5% | 91 | 834 |
| ML-DSA-44 | 2454 | 12.7% | 2451 | 22074 |
| ML-DSA-65 | 3343 | 17.3% | 3340 | 30075 |
| Falcon-512 | 688 | 3.6% | 689 | 6196 |
| SLH-DSA-128s | 7896 | 41.0% | 7893 | 71052 |
| hybrid(Ed25519+ML-DSA-65) | 3436 | 17.8% | 3430 | 30900 |

Aggregator verification throughput (full `verify_envelope` path, sequential, median of 3 runs), envelopes/s:

| config | 50 clients | 100 clients | 500 clients |
|---|---|---|---|
| Ed25519 | 8196 (6 ms total) | 7944 (13 ms total) | 8149 (61 ms total) |
| ML-DSA-44 | 18882 (3 ms total) | 21181 (5 ms total) | 20711 (24 ms total) |
| ML-DSA-65 | 17671 (3 ms total) | 17792 (6 ms total) | 17270 (29 ms total) |
| Falcon-512 | 17408 (3 ms total) | 17111 (6 ms total) | 17229 (29 ms total) |
| SLH-DSA-128s | 2348 (21 ms total) | 2264 (44 ms total) | 2330 (215 ms total) |
| hybrid(Ed25519+ML-DSA-65) | 7106 (7 ms total) | 7101 (14 ms total) | 7022 (71 ms total) |
