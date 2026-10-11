# UI plan

Stack: Next.js 16 App Router + TypeScript, Recharts, npm (Node 24, `engines` in package.json), FastAPI backend.
Run with `make ui`; test with `make ui-test`. Demos use `next build` + `next start` (7.5 GB RAM).
Types come from `docs/openapi.json` via `openapi-typescript`; the frontend talks to the backend only through `frontend/lib/api/`.

Global rules: each chart/table shows a "Source: <file>" caption taken from the API `source` field. Empty/missing data
shows an explicit empty state. Light/dark themes via CSS variables. `REPLAYED` and `LIVE` are two distinct, large badges:
LIVE = computed now by the backend in this session; REPLAYED = read from a stored receipt/file. ZK is always REPLAYED.
Diverged runs show a "DIVERGED at round N" marker and never a number; the D-012 note sits beside them.

| Route | Screen | Data needed | Endpoint(s) | Owner |
|---|---|---|---|---|
| `/` | Overview: A/B/C accuracy curves from stored results, headline table, links | scenario curves, scenario summary | `/api/results/scenarios_curves`, `/api/results/scenarios`, `/api/scenarios` | F1 |
| `/run` | Scenario runner: pick scenario or attack/defence, aggregator, seeds, rounds, run; live accuracy chart, accepted/rejected counts per round | run config, SSE rounds | `/api/scenarios`, `POST /api/runs`, `/api/runs/{id}/stream` | F2 |
| `/run` (section) | Rejection log: round, client, category, raw reason, gate; filter by category | `Rejection[]` from stream, or stored `rejections.csv` | stream, `/api/results/rejections` | F2 |
| `/zk` | ZK panel: per-round proof status, receipt cards with REPLAYED label, verify result, hardware | receipts, per-round status | `/api/receipts`, `/api/zk/rounds` | F2 |
| `/consensus` | Consensus panel: rounds, leader, votes, view changes (none: D-020), certificate chain, "Verify certificate (public keys only)" button | consensus view, verify | `/api/consensus/{run_id}`, `POST /api/certificates/verify` | F2 |
| `/overheads` | Overheads: signature sizes/times, envelope overhead, proof time/size/memory, round latency, bandwidth, hardware specs | signature and ZK bench | `/api/overheads` | F1 |
| `/attacks` | Attack matrix heatmap: attack x defence, actual outcomes incl. diverged cells and misses, colour-blind-safe scale | attack_matrix, rejections | `/api/results/attack_matrix`, `/api/results/rejections` | F2 |
| `/limitations` | Limitations list from `docs/limitations.md` grouped by its 5 headings | parsed limitations | `/api/limitations` | F1 |

Layout: left nav, top bar with theme toggle and a persistent "ZK: replay only" chip; backend status from `/api/health`.

Component ownership: F1 owns `frontend/` except `components/scenario/`, `components/consensus/`, `app/run/`.
F2 owns those three and also `app/zk`, `app/consensus`, `app/attacks` page files plus the shared `components/zk/` and `components/heatmap/`
(F1 creates empty route stubs for these four routes so navigation works; F2 replaces them).
Tests: B1 pytest in `tests/backend/`; Q Playwright in `tests/e2e/`.
