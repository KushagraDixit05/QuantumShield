# Toolchain check (2026-10-08)
Hardware: Intel i5-11260H (12 threads), 7.5 GB RAM, Linux 7.0, no GPU used.

| Item | Result |
|---|---|
| Python | 3.11.17 in `.venv` (via uv; system has only 3.12.3) |
| PyTorch | 2.14.1+cpu imports, tensor op OK |
| liboqs | 0.16.0 built from source by liboqs-python 0.16.0.1 (needs `cmake` from venv on PATH); installed to `~/_oqs` |
| ML-DSA-65 | pk 1952 B, sig 3309 B; verify True; tamper/wrong-message rejected (`tests/test_smoke.py`: 2 passed) |
| RISC Zero | rzup 0.5.0; r0vm / cargo-risczero 3.0.6, rust 1.97.0 |
| zkVM hello-world | `zk/hello`, real prove+verify, `RISC0_DEV_MODE=0`: `receipt=composite bytes=209570 prove_s=4.75 verify_ms=13.8 cycles=32768` |
| Peak RSS | 1.66 GB (`/usr/bin/time -v` over the whole `cargo run`, which includes compilation; prover-only RSS to be measured in Phase 3) |

Notes: the composite receipt is a real STARK (hash-based). Succinct/compressed receipts are an option for smaller proofs in Phase 3.
Install times: liboqs build ~3.3 min, `rzup install` ~13 min, first cargo build of the hello project ~6 min.
