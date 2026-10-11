# Agent G: OpenAPI types status

## Done
- `docs/openapi.json` regenerated (`.venv/bin/python -m backend.export_openapi`), `frontend/lib/api/schema.d.ts` generated (`npm run gen:api`).
- `frontend/lib/api/types.ts` rewritten: Hardware, Receipt(s), ZkRound(s), Vote (=ConsensusVote), ConsensusRound, ConsensusView (=ConsensusResponse), Certificate, CertVote, CertificateVerifyRequest (=VerifyRequest), CertificateVerifyResponse (=VerifyResponse), LimitationsResponse, HealthResponse (=Health), ScenariosResponse, Scenario, RunCreated are aliases of `components["schemas"][...]`. All old exported names kept. `components` is also re-exported.
- Shims (commented in the file): `RunRequest` (schema with `aggregator`/`live_zk` defaults optional for callers), `ResultsResponse` (rows narrowed to `Row[]`; schema says `unknown` cells).
- Hand-written, documented in the header: SSE `RunEvent` union, `Rejection`/`Reason`/`Gate` (only appear in SSE events), `OverheadsResponse`/`Table` (`/api/overheads` has no response model; schema is `unknown`).
- `frontend/scripts/check-api-schema.mjs` and `npm run check:api`.
- Schema-vs-hand-written differences now visible in types: `ZkRound.status` includes `unverified`; `Hardware.threads` is `number|null`; `Hardware.gpu_used` literal `false`; `Health.live_zk_enabled` and `ScenariosResponse.live_zk_enabled` are literal `false`; consensus has `run_id/seed/seeds_available`; `GET /api/certificates/{run_id}/{round}` returns `Certificate` (exported, not yet used by `client.ts`, which I did not extend).

## Blocked / needs (lead)
1. One real mismatch needs a component edit; `npm run typecheck` and `npm run build` fail until it is fixed:
   `frontend/components/consensus/ConsensusView.tsx:145` `title={r.model_hash}` -> `title={r.model_hash ?? undefined}`
   (schema: `ConsensusRound.model_hash: string | null`; the old hand-written type claimed `string`). Lint is clean. I did not shim this because a shim would hide a real null.
   Output: `components/consensus/ConsensusView.tsx(145,58): error TS2322: Type 'string | null' is not assignable to type 'string | undefined'.`
   `npm run build`: "Compiled successfully", then "Failed to type check" on that same error. Build not re-run after the fix (a `next dev` (pid 276277) was running during my build attempt).
2. Makefile wiring (not edited by me):
   - `make ui-gen`: `.venv/bin/python -m backend.export_openapi && cd frontend && npm run gen:api`
   - add `cd frontend && npm run check:api` to `make ui-test` (exits 1 and prints "Run `make ui-gen` to regenerate." when stale).
3. `backend/export_openapi.py` has no output-path option and is not mine to change; the check script uses `python -c` with identical serialization (`json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"`). If that serialization changes in export_openapi, update the script.

## check:api proof (committed files untouched; scratch copies via env vars API_CHECK_OPENAPI / API_CHECK_SCHEMA)
- Corrupted openapi.json copy (ref broken): exit 1,
  `check:api FAILED: <copy> is stale (differs from the live backend OpenAPI)` + `openapi-typescript could not process ... (invalid OpenAPI)` + `Run \`make ui-gen\` to regenerate.`
- Edited openapi.json copy (one summary text): both files reported stale.
- Corrupted schema.d.ts copy: `check:api FAILED: <copy> is stale (differs from openapi-typescript output of docs/openapi.json)`, exit 1.
- Real files: `check:api OK: docs/openapi.json and lib/api/schema.d.ts are up to date`, exit 0.
