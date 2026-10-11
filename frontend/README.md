# QuantumShield-FL frontend

Next.js 16 (App Router) + React 19 + Recharts + TypeScript. The Next.js here has breaking changes from older
versions: read `node_modules/next/dist/docs/` before changing framework-level code (see `AGENTS.md`).

## Requirements

- Node 24 (`engines`: `>=24 <25`)
- **npm** is the only package manager. Do not use pnpm or yarn; commit `package-lock.json`.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | dev server on :3000 (heavy; do not run together with `build` on a 7.5 GB machine) |
| `npm run build` / `npm start` | production build and server (use this for demos) |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run gen:api` | regenerate `lib/api/schema.d.ts` from `../docs/openapi.json` with `openapi-typescript` |

## Configuration

`NEXT_PUBLIC_API_URL` is the backend base URL (default `http://127.0.0.1:8000`). It is inlined at build time.

## Typed API client

All backend access goes through `lib/api/` (import from `@/lib/api`); no component calls `fetch` itself.

- `lib/api/types.ts`: types for every payload in `docs/api_contract.md`. Hand-written until the backend exports
  `docs/openapi.json`.
- `npm run gen:api` writes `lib/api/schema.d.ts`. After the first generation, alias the interfaces in `types.ts` to
  `components["schemas"][...]` so the generated schema is the source of truth (only that file changes).
- `lib/api/client.ts`: one fetch wrapper per endpoint, `ApiError`, and `streamRun(id, onEvent, onFail)` (EventSource, typed `RunEvent`).
- `lib/api/useApi.ts`: `useApi(fetcher)` hook returning `{data, error, loading}`.

## Layout of the code

- `components/shared/`: SourceCaption, Badge / ReplayedBadge / LiveBadge, DivergedMarker, EmptyState, Card, ChartFrame, DataTable, Async, PageHeader (import from `@/components/shared`).
- `components/shell/`: nav, top bar, theme toggle, backend health.
- `lib/theme/palette.ts`: colour-blind-safe categorical, sequential and diverging scales.
- Theme: CSS variables in `app/globals.css`, `data-theme` on `<html>` set by an inline script before first paint; without a stored choice `prefers-color-scheme` applies.

The frontend holds no result data. Anything numeric is fetched from the backend, which reads the repository's result files.
