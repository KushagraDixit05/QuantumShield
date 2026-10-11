# QuantumShield-FL User Guide

This guide shows how to set up the project, start the web UI, and read what it shows. For the design and the
claims, read `README.md`. For what the project does **not** prove, read `docs/limitations.md` first.

## 1. What you are looking at

QuantumShield-FL is a small decentralized federated-learning (FL) pipeline. Every model update carries a
post-quantum signature (ML-DSA-65, hybrid with Ed25519) and, in the ZK stage, a RISC Zero proof. Four simulated
aggregator nodes finalize each round by a 2f+1 signed vote (n=4, f=1).

The web UI lets you run attack scenarios, look at the stored zero-knowledge receipts, check consensus votes, and
compare overheads. It is evidence from one machine, a small model (2,410 parameters) and a simulated network. It is
not a security proof.

## 2. Requirements

- Linux, with a C toolchain (liboqs is built from source by `liboqs-python`)
- Python 3.11, in the project virtualenv `.venv`. Always use `.venv/bin/python`: the signature library (`oqs`) is only installed there.
- Node 24 and **npm** (the only package manager used; do not use pnpm or yarn)
- About 7.5 GB RAM. The UI never proves anything, but a real proof (`make phase3`) needs about 2.4 GB for about 6 minutes.
- Optional, only for new ZK receipts and `tests/zk`: the RISC Zero toolchain (`make zk-build`)

## 3. One-time setup

From the project root:

```
make setup        # creates .venv and installs requirements.txt
make ui-install   # npm install in frontend/ and tests/e2e/
```

## 4. Start and stop the UI

```
make ui
```

This rebuilds the frontend, then starts both servers:

| Part | Address |
|---|---|
| UI | http://127.0.0.1:3000 |
| Backend API | http://127.0.0.1:8000 (interactive API docs at `/docs`) |

- The backend needs a few seconds to import its libraries after the UI is up. If a page says **backend unreachable**, wait a moment and reload.
- Press **Ctrl-C** in that terminal to stop both servers.
- Ports 8000 and 3000 must be free. The backend only accepts browser requests from `localhost`/`127.0.0.1` on ports 3000 and 3001.
- To run only the backend: `make api`.
- Quick check: `curl http://127.0.0.1:8000/api/health` should return `{"ok":true,"live_zk_enabled":false,...}`.

`make ui` always rebuilds because `make ui-test` leaves a build that points at a different backend port (8011), and
serving that build would break every page.

The top bar shows the backend status and a permanent **ZK: replay only** chip. There is a light/dark theme toggle.

## 5. Using the screens

The left navigation has seven pages.

### Overview
Accuracy curves for the three standard scenarios (seed 0) and a summary table over all stored seeds. Read it to see
the headline result: with the defence on, benign accuracy is unchanged; with no defence, the poisoned run diverges.

### Run (scenario runner)
Run a scenario live and watch it round by round.

1. Pick **Preset A / B / C**, or **Custom attack and defence**:
   - **A**: benign, no attack
   - **B**: poisoned client, plain FedAvg (no defence)
   - **C**: poisoned client, QuantumShield on
2. For a custom run, choose the attack (`none`, `scaled`, `forged`, `replay`), the defence (`on` or `off`) and the aggregator (`fedavg`, `norm_filter`, `median`, `clip`). The **Attack enabled** box turns the attack on or off.
3. Tick the seeds (0 to 4), set the number of rounds (1 to 50; the stored results use 10).
4. Press **Run**. The output is marked **LIVE**: it is computed now by the backend.

You will see accuracy per round (one line per seed), accepted and rejected update counts per round, and a per-seed
final result. Runs go through a queue and execute one at a time. There is no cancel: **Stop watching** only closes
the stream, and the backend finishes the run. Each run shows a run id; keep it for the Consensus page.

**Rejection log** (below the runner). Every rejected update with its round, client, category and the exact reason
string. Categories are bad signature, wrong round, norm bound exceeded, failed proof, replay, not in quorum and
other. You can switch between this session's rejections and the stored `demo/results/rejections.csv`. A rejection for
`norm_bound_exceeded` is labelled **plaintext norm gate (not ZK)**: the live scenarios check the norm bound directly
and do not generate a proof.

### ZK
Replay only. Live proving takes about 6 minutes and 2.4 GB per proof, so this page shows the four stored receipts
and what the verifier says about them. Nothing is proved when you open it.

- Every result carries a **REPLAYED** badge and a label of the form: *replayed from receipt `<id>`, generated `<date>`, on `<hardware>`*.
- The receipt id is the first 12 hex characters of the receipt file's SHA-256. "Generated" is the file's modification time. The receipt files carry no metadata of their own.
- The hardware comes from `demo/results/zk_bench.md` and `docs/zk_cost.md`.
- Rows marked **NO RECEIPT** are updates the prover could not prove (for example the attacker's scaled update).

### Consensus
1. Run a scenario on the Run page. Its run id is remembered in your browser tab and loaded here automatically, or paste a run id and press **Load**.
2. The table lists each round with the leader (always node 0), votes, quorum (3 of 4), whether it finalized, equivocators and bad votes.
3. Press **Verify certificate (public keys only)** on a round. The backend checks that round's signed votes using public keys only; no secret key is used.

Limits to know: this consensus has a fixed leader and no view changes (deferred, decision D-020). A "certificate" here
is the round's set of signed votes, so the check verifies those votes and the 2f+1 quorum; it is not a chained
certificate.

### Overheads
Signature and public-key sizes and times, per-update envelope overhead, verification throughput, ZK prove and verify
time, receipt size and peak memory, round latency and bandwidth, and the hardware the numbers were measured on.
Timings come from a single machine and vary roughly 20% between runs.

### Attack matrix
A heatmap of attack against defence with the actual outcomes, including failures and misses. Each cell prints its
values (mean final accuracy, spread, number of seeds, how many diverged, how many updates were rejected), so colour
is never the only signal. Hover or focus a cell for details; a table view is available.

### Limitations
The limitations list from `docs/limitations.md`, grouped by its headings. Read it before relying on any number.

## 6. Reading the results honestly

- **Sources.** Every chart and table shows the file it came from (`Source: ...`). Stored results are in `demo/results/`.
- **DIVERGED.** In a poisoned run without the defence, the model leaves the int64 fixed-point range and the run stops. The stored files record such rounds as accuracy `0.0`. That is a convention (decision D-012), not a measured accuracy. The UI shows these as **DIVERGED** and never plots them as 0. A run stops at its divergence round, so later rounds do not exist.
- **Standard deviation** is the population standard deviation (n), as in `demo/results/scenarios_summary.md`.
- **Replay attack.** Replayed updates are rejected in both modes, so that row does not show an advantage for the defence.
- **LIVE vs REPLAYED.** LIVE means the backend computed it just now (the Run page). REPLAYED means it is read from a stored file or receipt. ZK results are always REPLAYED.

## 7. Working from the command line

```
make demo        # regenerate demo/results: scenarios, rejection log, ZK check, figures, overhead table (no prover)
make test        # full pytest suite (tests/zk needs the built qs-zk binary: make zk-build)
make ui-test     # backend tests, schema check, frontend lint/typecheck/build, browser tests
make ui-gen      # regenerate the OpenAPI types after changing the backend schema
make phase3      # produce new real ZK receipts: about 6 minutes and 2.4 GB per proof
```

Run one scenario without the UI:

```
.venv/bin/python -m demo.run_demo --stage scenarios --attack scaled --defence on --seeds 0
```

Notes:
- `make ui-test` uses its own ports (8011 and 3001), so it can run while the UI is open, but do not run it together with other heavy jobs on a 7.5 GB machine. Run `make ui` again afterwards (it rebuilds).
- Only one prover may run at a time. Proving takes the lock file `.zk_prove.lock`, and the UI never proves.

## 8. Where things are

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (runs, queue, results, receipts, certificates) |
| `frontend/` | Next.js UI (npm, Node 24) |
| `demo/results/` | Stored results and receipts that the UI displays |
| `fl/`, `pq/`, `zk/`, `consensus/`, `attacks/` | The FL, signature, ZK, consensus and attack code. The UI only calls it. |
| `tests/backend`, `tests/hardening`, `tests/e2e` | API tests, certificate tests, browser tests |
| `docs/api_contract.md` | Every API endpoint and the event stream format |
| `docs/limitations.md`, `docs/decisions.md` | What is not proved; design decisions (D-012 divergence, D-020 deferred consensus features) |
| `docs/ui_report.md`, `docs/ui_issues.md` | UI test results and known issues |

## 9. Troubleshooting

| Symptom | What to do |
|---|---|
| Pages show **backend unreachable** | The backend is still starting (wait a few seconds), or it is not running (`make api`). If the UI was built against another API address, run `make ui-build`. |
| `port already in use` | Run `ss -ltnp` and look for ports 8000 and 3000, then stop that process (or the old `make ui`). |
| Out of memory | Use `make ui` (production build), not `npm run dev`. Do not run `make ui-test`, a proof and the UI together. |
| Run says it is queued | Only one run executes at a time; yours starts when the current one finishes. |
| A request with `live_zk: true` returns 422 | By design: live proving is disabled in the UI backend. |
| Consensus page is empty | Run a scenario first, then open Consensus, or paste its run id. |

Known open UI issues are listed in `docs/ui_issues.md` (for example, the Run page shows per-seed results but not a
mean ± std line over the chosen seeds).
