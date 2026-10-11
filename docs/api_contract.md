# API contract (backend/ <-> frontend/)

Base URL `http://127.0.0.1:8000`. All bodies are JSON except the SSE stream. The OpenAPI schema is exported to
`docs/openapi.json`, and the frontend's typed client is generated from it. If this document and the schema disagree,
fix the document.

Every payload that carries numbers from a file includes `source`: the repo-relative path(s) it was read from.
The backend never invents, interpolates or fills in numbers; a missing file gives `404 {"detail": "<file> not found"}`.

## Shared types

```
Reason = "bad_signature" | "wrong_round" | "norm_bound_exceeded" | "bad_proof" | "replay" | "not_in_quorum" | "other"
RawReason = string   // the exact string from the code, e.g. "bad_proof:missing_proof_hash", "replayed_nonce", "stale_key"
Rejection = { round: int, client: int | null, reason: Reason, raw_reason: RawReason, gate: "signature" | "plaintext_norm_gate" | "zk" | "consensus" }
```

Reason mapping (backend `reasons.py`, one table, unit-tested):
`bad_signature`, `scheme_downgrade`, `unsigned`, `unknown_key`, `revoked_key`, `key_identity_mismatch` -> `bad_signature`;
`wrong_round`, `wrong_model_hash` -> `wrong_round`; `norm_bound_exceeded` -> `norm_bound_exceeded` (gate `plaintext_norm_gate`, not ZK, D-013);
`bad_proof:*` -> `bad_proof`; `replayed_nonce`, `duplicate_submission`, `stale_key` -> `replay`; a round that finalizes
nothing (no 2f+1 quorum) -> `not_in_quorum` with `client: null`; everything else -> `other`. `raw_reason` is always kept.
`stale_key` is mapped to `replay` only because `demo/results/rejections.csv` shows it together with `wrong_round` on replay runs; the UI shows `raw_reason` beside it.

## GET /api/scenarios
Response `ScenariosResponse`:
```
{ source: ["demo/run_demo.py:158", "demo/plot.py:23", "configs/demo.yaml"],
  scenarios: [{ id: "A"|"B"|"C", label: string, attack: "none"|"scaled", defence: "off"|"on", description: string }],
  attacks: ["none","scaled","forged","replay"],
  aggregators: ["fedavg","norm_filter","median","clip"],     // keys of fl.aggregate.DEFENCES
  default_seeds: int[], default_rounds: int,
  live_zk_enabled: false }                                    // always false
```

## POST /api/runs
Request `RunRequest`:
```
{ scenario?: "A"|"B"|"C",            // shorthand; sets attack/defence
  attack?: "none"|"scaled"|"forged"|"replay",
  defence?: "on"|"off",              // "on" = hybrid signatures + plaintext norm gate
  aggregator: "fedavg"|"norm_filter"|"median"|"clip" = "fedavg",
  seeds: int[] (1..5 entries, each 0..10^6),
  rounds?: int (1..50),
  live_zk: boolean = false }
```
Either `scenario` or both `attack` and `defence` must be given.
Response `201 {"id": string, "queue_position": int}`.
Errors: `422` for invalid body **and for any `live_zk: true`** (`detail: "live ZK proving is disabled on this server"`); `409` is not used because runs queue.
Runs execute one job at a time in a single worker. A run is not started while `.zk_prove.lock` is held by a prover; it waits and the stream reports `queued`.

## GET /api/runs/{id}/stream  (text/event-stream)
One SSE message per event, `data:` carries JSON with a `type` field. The stream closes after `done` or `error`. Unknown id -> 404. Reconnecting replays all events from the start.

```
{ type: "queued",  position: int }
{ type: "started", seed: int, attack: string, defence: string, aggregator: string, rounds: int }
{ type: "round",   seed: int, round: int, accuracy: float | null, diverged: boolean,
                   accepted: int[], accepted_count: int, rejected_count: int, rejections: Rejection[],
                   latency_ms: float | null, model_hash: string | null,
                   consensus: { leader: int, votes: int, quorum: int, finalized: boolean } }
{ type: "seed_done", seed: int, final_accuracy: float | null, diverged_round: int | null, convention_note: string | null }
{ type: "done",    results: [seed_done...], source: "computed live by backend.runner (mirrors demo/run_demo.py:run_scenario)" }
{ type: "error",   message: string }
```
`accuracy` is `null` for a diverged round. It is never `0.0`. `convention_note` quotes D-012 when diverged (the 0.0 appears only in
stored CSV/JSON, where the UI explains it).

## GET /api/results/{name}
`name` is one of: `scenarios`, `scenarios_curves`, `rejections`, `baseline`, `phase2_fl`, `phase3_fl`, `sig_bench`,
`sig_bench_overhead`, `sig_bench_throughput`, `zk_bench`, `zk_consensus`, `overheads`, `attack_matrix`. Unknown name -> 404.
Response `ResultsResponse`:
```
{ name: string, source: string[],           // e.g. ["demo/results/scenarios.csv"]
  columns: string[], rows: object[],        // CSV rows with int/float parsing; blank cells -> null
  json?: object,                            // for .json files (scenarios_curves = demo/results/scenarios.json)
  markdown?: string,                        // for overheads
  diverged_note?: { decision: "D-012", text: string } }
```
`attack_matrix` is computed by the backend from `demo/results/scenarios.csv` (attack x defence, mean/std final accuracy over seeds,
number of seeds, number diverged, rejected count). It is not a stored file, and `source` says so. Cells with divergence carry
`diverged: k of n`; they are never rendered as a plain accuracy.

## GET /api/receipts
Replay-only. Response `ReceiptsResponse`:
```
{ source: ["demo/results/zk/", "demo/results/zk_bench.md", "docs/zk_cost.md"],
  hardware: { cpu, threads, ram, os, gpu_used: false, zkvm, source },
  receipts: [{ id: string,                 // first 12 hex chars of sha256(receipt file)
               path: string, bytes: int, generated: ISO8601,   // file mtime; stated as such
               journal_bytes: int, round: int | null, client: int | null,
               image_id: string | null, prove_s: float | null, cycles: int | null, peak_rss_mb: float | null,
               verified: boolean | null, verify_s: float | null, verify_error: string | null,
               replayed: true,
               label: string }] }          // "replayed from receipt <id>, generated <date>, on <hardware>"
```
`verified` comes from `zk.bridge.cli.verify_receipt` (verify only, no prover lock needed; no proving). `replayed` is the literal `true` and there is no field that can say "live".
Also `GET /api/zk/rounds` -> per-round proof status from `zk_consensus.csv` and `phase3_fl.csv` (`status: "verified"|"no_receipt"|"rejected"`, `reason`, `receipt_id`, `label`), with the same `replayed: true` and `label`.

## GET /api/consensus/{run_id}
Consensus view of a finished or running run, taken from `Node` state of the backend runner (no consensus code changed):
```
{ n: 4, f: 1, quorum: 3, leader: 0, leader_policy: "fixed (no rotation)", view_changes: [] , view_changes_note: "not implemented, see D-020",
  rounds: [{ round, model_hash, votes: [{ node, signer_alg, hash, valid }], finalized, equivocators: int[], bad_votes: int, certificate_id: string | null }] }
```
`certificate_id` = sha256 prefix of the canonical vote set. A "certificate" is the round's signed votes (see docs/ui_issues.md UI-002).

## POST /api/certificates/verify
Request `{ run_id: string, round: int }` (or `{ certificate: Certificate }` for a pasted one).
Verifies with a secret-free registry (`KeyRegistry.from_snapshot`, public keys only), calling `Verifier.verify_vote` per vote.
Response `{ valid: boolean, quorum_met: boolean, checked: [{ node, ok, reason }], public_keys_only: true, source: "pq/policy.py Verifier.verify_vote" }`.
Never needs a secret key; the handler never touches `sk`.

## GET /api/limitations
`{ source: "docs/limitations.md", sections: [{ title, items: [{ n: int, text: string }] }] }`, parsed from the file, not retyped.

## GET /api/overheads
```
{ hardware: {...}, 
  signatures: { source: "demo/results/sig_bench.csv", rows: [...] },       // sizes and ms
  envelope: { source: "demo/results/sig_bench_overhead.csv", rows: [...] },
  throughput: { source: "demo/results/sig_bench_throughput.csv", rows: [...] },
  zk: { source: "demo/results/zk_bench.csv", rows: [...] },                 // prove_s, verify_s, receipt_bytes, peak_rss_kb
  round: { source: "demo/results/scenarios.csv", mean_round_latency_ms, mean_update_env_bytes }, // per attack/defence
  markdown: { source: "demo/results/overheads.md", text: string } }
```

## GET /api/health
`{ ok: true, live_zk_enabled: false, prover_lock_held: boolean, queue_length: int }`.

## Errors
FastAPI default `{ "detail": string | ValidationError[] }`.

## Additions made by B1 (implemented; `docs/openapi.json` is authoritative)
- `GET /api/zk/rounds` `status` may also be `"unverified"` (receipt exists but verification could not run). Never shown as verified.
- `GET /api/certificates/{run_id}/{round}` returns a pasteable certificate. `GET /api/consensus/{run_id}` takes optional `?seed=`.
- `POST /api/certificates/verify`: `valid` = every supplied vote verifies AND at least 3 distinct nodes voted the same hash; `quorum_met` is the second condition alone. Pasted certificates are checked against the run's own public registry.
- Receipt `prove_s`, `cycles`, `peak_rss_mb` come from `demo/results/phase3_fl.csv` (no `*.stats.json` files exist). See docs/ui_issues.md UI-B1-5, UI-B1-6.
