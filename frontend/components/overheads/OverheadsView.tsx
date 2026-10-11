"use client";
import { Async, Badge, Card, DataTable, EmptyState, ReplayedBadge, SourceCaption, type Column } from "@/components/shared";
import { getOverheads, useApi, type Hardware, type OverheadsResponse, type Row } from "@/lib/api";
import { fmtBytes, fmtNum } from "@/lib/format";
import { BarsChart } from "./BarsChart";
import { ThroughputChart } from "./ThroughputChart";

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const range = (rows: Row[], k: string, f: (n: number) => string) => {
  const v = rows.map((r) => num(r[k])).filter((x): x is number => x !== null);
  if (!v.length) return "n/a";
  const lo = Math.min(...v), hi = Math.max(...v);
  return lo === hi ? f(lo) : `${f(lo)} to ${f(hi)}`;
};

function HardwareList({ hw }: { hw: Hardware }) {
  const entries = Object.entries(hw).filter(([k, v]) => k !== "source" && v !== null && v !== undefined);
  return (
    <dl className="qs-kv">
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: "contents" }}>
          <dt>{k}</dt>
          <dd>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The `round` block is only loosely specified; show whatever scalar / per-group values it carries. */
function roundRows(round: OverheadsResponse["round"]): Row[] {
  if (Array.isArray(round.rows)) return round.rows;
  const lat = round.mean_round_latency_ms, env = round.mean_update_env_bytes;
  const toMap = (v: unknown): Record<string, unknown> =>
    v && typeof v === "object" ? (v as Record<string, unknown>) : typeof v === "number" ? { all: v } : {};
  const L = toMap(lat), E = toMap(env);
  return [...new Set([...Object.keys(L), ...Object.keys(E)])].map((k) => ({
    group: k,
    mean_round_latency_ms: num(L[k]),
    mean_update_env_bytes: num(E[k]),
  }));
}

function View({ o }: { o: OverheadsResponse }) {
  const sig = o.signatures.rows;
  const zk = o.zk.rows;
  const rr = roundRows(o.round);
  const rcols: Column<Row>[] = rr[0] ? Object.keys(rr[0]).map((k) => ({ key: k, header: k.replace(/_/g, " "), numeric: k !== "group" })) : [];
  const envRows = o.envelope.rows;
  // Benchmark rows are not receipts (no receipt id) and the CSV records no date, so the label says exactly that.
  const zkLabel = (run: unknown) => `replayed from stored benchmark ${String(o.zk.source)}, run ${String(run)} (no receipt id; generation date not recorded in the file), on ${String(o.hardware.cpu ?? "hardware not reported")}`;
  const zkCols: Column<Row>[] = [
    { key: "run", header: "run", numeric: true },
    { key: "kind", header: "kind" },
    { key: "prove_s", header: "prove (s)", numeric: true },
    { key: "verify_s", header: "verify (s)", numeric: true },
    { key: "receipt_bytes", header: "receipt", numeric: true, render: (r) => fmtBytes(r.receipt_bytes) },
    { key: "peak_rss_kb", header: "peak memory", numeric: true, render: (r) => (num(r.peak_rss_kb) === null ? "n/a" : `${fmtNum((r.peak_rss_kb as number) / 1024, 0)} MB`) },
    { key: "cycles", header: "cycles", numeric: true },
    { key: "po2", header: "po2", numeric: true },
    { key: "label", header: "provenance", render: (r) => zkLabel(r.run) },
  ];
  return (
    <>
      <Card title="Signature sizes and times">
        <BarsChart title="Key and signature sizes" subtitle="Bytes on the wire per algorithm." source={o.signatures.source} rows={sig} xKey="alg" unit="bytes" log
          series={[{ key: "pk_bytes", label: "public key" }, { key: "sig_bytes", label: "signature" }]} />
        <BarsChart title="Keygen, sign and verify time" subtitle="Mean milliseconds per operation." source={o.signatures.source} rows={sig} xKey="alg" unit="ms" log
          series={[{ key: "keygen_ms_mean", label: "keygen" }, { key: "sign_ms_mean", label: "sign" }, { key: "verify_ms_mean", label: "verify" }]} />
      </Card>

      <Card title="Envelope overhead">
        <BarsChart title="Signature overhead per update envelope" subtitle="Extra bytes a signed envelope adds to one client update." source={o.envelope.source} rows={envRows} xKey="config" unit="bytes"
          series={[{ key: "envelope_overhead_bytes", label: "envelope overhead" }, { key: "vote_overhead_bytes", label: "vote overhead" }]} />
        <DataTable columns={envRows[0] ? Object.keys(envRows[0]).map((k) => ({ key: k, header: k.replace(/_/g, " "), numeric: k !== "config" })) : []} rows={envRows} />
        <SourceCaption source={o.envelope.source} />
      </Card>

      <Card title="Throughput">
        <ThroughputChart rows={o.throughput.rows} source={o.throughput.source} />
      </Card>

      <Card title="ZK proving and verification" badge={<ReplayedBadge label="stored benchmark; nothing is proved when you load this page" />}>
        {zk.length > 0 && (
          <div className="qs-stats">
            <div className="qs-stat"><b>{range(zk, "prove_s", (n) => `${fmtNum(n, 1)} s`)}</b><span>prove time ({zk.length} runs)</span></div>
            <div className="qs-stat"><b>{range(zk, "verify_s", (n) => `${fmtNum(n, 3)} s`)}</b><span>verify time</span></div>
            <div className="qs-stat"><b>{range(zk, "receipt_bytes", fmtBytes)}</b><span>receipt size</span></div>
            <div className="qs-stat"><b>{range(zk, "peak_rss_kb", (n) => `${fmtNum(n / 1024, 0)} MB`)}</b><span>peak memory</span></div>
          </div>
        )}
        <p className="muted" style={{ fontSize: "0.85rem" }}>{zkLabel(`1 to ${zk.length}`)}</p>
        <h3>Per run</h3>
        <DataTable columns={zkCols} rows={zk} empty="No ZK benchmark rows" />
        <SourceCaption source={o.zk.source} />
      </Card>

      <Card title="Round latency and update bandwidth" source={o.round.source}>
        {rr.length ? <DataTable columns={rcols} rows={rr} /> : <EmptyState title="No round latency data in the response" />}
      </Card>

      <Card title="Hardware" source={o.hardware.source ?? "not reported"}>
        <HardwareList hw={o.hardware} />
        <p style={{ marginTop: 10 }}>
          <Badge tone="neutral">timings are single-machine and vary about 20% run to run (limitation 18)</Badge>
        </p>
      </Card>

      <Card title="Summary written by the benchmark" source={o.markdown.source}>
        <pre className="qs-pre mono" style={{ maxHeight: "none" }}>{o.markdown.text}</pre>
      </Card>
    </>
  );
}

export function OverheadsView() {
  const s = useApi(getOverheads);
  return (
    <Async state={s} what="overheads">
      {(o) => <View o={o} />}
    </Async>
  );
}
