"use client";
import { useMemo, useState } from "react";
import { Badge, Card, DataTable, EmptyState, LiveBadge, ReplayedBadge, SourceCaption, type Column } from "@/components/shared";
import { getResults, useApi } from "@/lib/api";
import { REASONS, REASON_LABEL, storedRow, type LogRow } from "./reasons";

const GATE_LABEL: Record<string, string> = {
  signature: "signature check",
  plaintext_norm_gate: "plaintext norm gate (not ZK)",
  zk: "ZK proof",
  consensus: "consensus quorum",
};

export function RejectionLog({ live }: { live: LogRow[] }) {
  const [view, setView] = useState<"live" | "stored">("live");
  const [cat, setCat] = useState<string>("all");
  const stored = useApi(() => (view === "stored" ? getResults("rejections") : Promise.resolve(null)), [view]);

  const rows: LogRow[] = useMemo(
    () => (view === "live" ? live : (stored.data?.rows ?? []).map(storedRow)),
    [view, live, stored.data],
  );
  const shown = cat === "all" ? rows : rows.filter((r) => r.reason === cat);
  const counts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const r of rows) m[r.reason] = (m[r.reason] ?? 0) + 1;
    return m;
  }, [rows]);

  const cols: Column<LogRow>[] = [
    ...(view === "stored" ? [{ key: "scenario", header: "stored run" } as Column<LogRow>] : []),
    { key: "round", header: "round", numeric: true },
    { key: "seed", header: "seed", numeric: true },
    { key: "client", header: "client", numeric: true, render: (r) => (r.client === null ? <span className="muted">round-level (no client)</span> : r.client) },
    {
      key: "reason",
      header: "category",
      render: (r) => <Badge tone={r.reason === "norm_bound_exceeded" ? "warn" : "neutral"}>{REASON_LABEL[r.reason]}</Badge>,
    },
    { key: "raw_reason", header: "raw reason", render: (r) => <span className="mono">{r.raw_reason}</span> },
    { key: "gate", header: "gate", render: (r) => GATE_LABEL[r.gate] ?? r.gate },
  ];

  return (
    <Card
      title="Rejection log"
      badge={view === "live" ? <LiveBadge label="from the run stream above" /> : <ReplayedBadge label="stored file demo/results/rejections.csv, not computed now" />}
    >
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
        <div role="group" aria-label="Rejection log source" style={{ display: "flex", gap: 6 }}>
          <button type="button" className="qs-btn" aria-pressed={view === "live"} onClick={() => setView("live")} style={view === "live" ? { fontWeight: 700, borderWidth: 2 } : undefined}>
            This session&apos;s run
          </button>
          <button type="button" className="qs-btn" aria-pressed={view === "stored"} onClick={() => setView("stored")} style={view === "stored" ? { fontWeight: 700, borderWidth: 2 } : undefined}>
            Stored (rejections.csv)
          </button>
        </div>
        <label style={{ fontSize: "0.85rem" }}>
          Category{" "}
          <select value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="all">all ({rows.length})</option>
            {REASONS.map((r) => (
              <option key={r} value={r}>
                {REASON_LABEL[r]} ({counts[r] ?? 0})
              </option>
            ))}
          </select>
        </label>
      </div>
      {view === "stored" && stored.loading && <p className="muted" role="status">Loading stored rejections...</p>}
      {view === "stored" && stored.error && <EmptyState title="Stored rejections unavailable" error={stored.error} />}
      {(view === "live" || stored.data) && (
        <>
          <DataTable
            columns={cols}
            rows={shown}
            empty={view === "live" ? "No rejections received yet (a run with no attack rejects nothing)." : "No rows match this filter."}
          />
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            Norm-bound rejections come from a plaintext check of the update&apos;s norm (D-013); no zero-knowledge proof is involved. The stored file has
            no category column: categories there are derived from the raw reason using the mapping in docs/api_contract.md. <code>stale_key</code> is
            mapped to replay; read it with its raw reason.
          </p>
        </>
      )}
      <SourceCaption
        source={view === "stored" ? (stored.data?.source ?? ["demo/results/rejections.csv"]) : "run event stream, GET /api/runs/{id}/stream (computed live by backend.runner)"}
      />
    </Card>
  );
}
