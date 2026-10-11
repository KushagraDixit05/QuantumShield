# ui-B1 status (backend)

## Done
- `backend/` rebuilt as modules: `main` (app, CORS localhost/127.0.0.1 on :3000/:3001), `schemas`, `run_queue` (single worker), `runner`, `reasons`, `results`, `receipts`, `hardware`, `certificates`, `limitations`, `overheads`, `common`, `export_openapi`.
- Every endpoint in `docs/api_contract.md`: scenarios, runs (POST + SSE stream), results (13 names), receipts, zk/rounds, consensus, certificates/verify, limitations, overheads, health.
- `docs/openapi.json` exported with `.venv/bin/python -m backend.export_openapi`.
- `tests/backend/` (86 tests, about 6 s). Old `tests/test_backend.py` ported (health, results, run stream, bad input, unknown run) and deleted.
- Runner drift test: fedavg accuracies, accepted sets, rejects, divergence round identical to `demo.run_demo.run_scenario` (scaled/on, none/off, replay/on, forged/on, 3 rounds; scaled/off 9 rounds for the divergence case).
- No prover is called anywhere. `live_zk: true` -> 422. A run waits (emitting `queued` again) while `.zk_prove.lock` is held (non-blocking `flock` probe, released at once).
- Receipts: all 4 real receipts verify (`verified: true`, about 0.2 s each) against an expected public journal rebuilt from `configs/phase3.yaml` (same inputs as `zk_stage` / `run_phase3`). A tampered receipt gives `verified: false`; a missing journal gives `verified: null` with a reason.
- Certificates implemented (not blocked): public-snapshot registry + `Verifier.verify_vote`, no secret key touched.

## Design notes
- `valid` = every supplied vote verifies AND >= 2f+1 distinct nodes voted the same hash. `quorum_met` is the second part alone. A pasted certificate is checked against the run's own public registry, never keys supplied by the paste.
- `rejected_count` counts client-level rejections only (the round-level `not_in_quorum` entry is in `rejections` but not in the count).
- A round with no 2f+1 matching votes ends the seed (as in run_scenario) with `final_accuracy: null`; only exercised in a test with silent nodes.
- `attack_matrix` mean/std exclude diverged seeds; cells carry `diverged: "k of n"`, `accuracy_is_plain: false`, and `mean_final_acc: null` if all seeds diverged.
- Extra: `GET /api/certificates/{run_id}/{round}` (pasteable certificate), `?seed=` on `/api/consensus/{run_id}`, `status: "unverified"` in `/api/zk/rounds`. See `docs/ui_issues.md` (UI-B1-*); the contract should be updated to list them.

## Blocked
Nothing.

## Needs
- Contract owner: list the extras above in `docs/api_contract.md`. `docs/ui_issues.md` did not exist and `api_contract.md` cites UI-002; that entry is not defined there (B1 entries are UI-B1-1..6).
- Run with `.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` (`make api`).
- `receipts` imports `experiments.run_phase3` and loads the digits data on the first `/api/receipts` call (about 1 s), then caches.
