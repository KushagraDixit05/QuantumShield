# UI F1 status (shell and data layer)

## Done
- Shell: left nav, top bar (theme toggle, persistent "ZK: replay only" chip, /api/health indicator), CSS-variable themes, no-flash inline script.
- Typed client `frontend/lib/api/` (all contract endpoints, `streamRun`, `useApi`), types hand-written in `types.ts`.
- Shared components `frontend/components/shared/`, palette `frontend/lib/theme/palette.ts`.
- Pages: `/` (A/B/C curves with diverged handling, summary table), `/overheads`, `/limitations`. Stubs: `/run`, `/zk`, `/consensus`, `/attacks`.
- package.json: engines, scripts (dev/build/start/lint/typecheck/gen:api), openapi-typescript dev dependency. README rewritten.
- `npm run lint`, `npm run typecheck`, `npm run build` pass.

## Blocked / not verified
- `docs/openapi.json` did not exist: `npm run gen:api` not run; `lib/api/schema.d.ts` absent. Types are hand-written from the contract.
- No visual check against a live backend (backend not ready); pages were only type-checked and built. Field names in `/api/overheads` `round` block and `signatures/envelope/throughput` rows were taken from the CSV headers and are rendered defensively.
- Diverging palette arms are not run through the dataviz validator (noted in palette.ts).

## Needs
- B1: export docs/openapi.json; confirm shape of `/api/overheads` `round` and `/api/results/scenarios_curves` `json` (`{rounds, seed, scenarios:{A,B,C}}`).
- F2: see shared component list in the final report; replace stubs in app/run, app/zk, app/consensus, app/attacks.
