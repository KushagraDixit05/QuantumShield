"use client";
import { Async, Badge, Card, DataTable, ReplayedBadge, SourceCaption, type Column } from "@/components/shared";
import { getReceipts, getZkRounds, useApi, type Receipt, type ZkRound } from "@/lib/api";
import { fmtBytes, fmtNum } from "@/lib/format";

function Verified({ v }: { v: boolean | null }) {
  if (v === true) return <Badge tone="good">&#10003; verified</Badge>;
  if (v === false) return <Badge tone="bad">&#10007; verification failed</Badge>;
  return <Badge tone="warn">? verification unknown</Badge>;
}

function StatusBadge({ s }: { s: ZkRound["status"] }) {
  if (s === "verified") return <Badge tone="good">&#10003; verified</Badge>;
  if (s === "rejected") return <Badge tone="bad">&#10007; rejected</Badge>;
  return <Badge tone="neutral">no receipt</Badge>;
}

export function ZkView() {
  const receipts = useApi(getReceipts);
  const rounds = useApi(getZkRounds);

  return (
    <>
      <Card title="Replay only">
        <p style={{ margin: 0, maxWidth: "75ch" }}>
          Nothing on this page was proved now. Each result is read from a receipt file already stored in the repository and checked with the verifier only
          (no prover, no proving). &quot;Generated&quot; is the receipt file&apos;s modification time, not a claim about when a proof ran. Real proofs exist for a
          small set of round/client pairs only (see limitations 3 and 4).
        </p>
      </Card>

      <Card title="Per-round proof status" badge={<ReplayedBadge label="stored zk_consensus.csv and phase3_fl.csv" />}>
        <Async state={rounds} what="per-round proof status">
          {(r) => {
            const cols: Column<ZkRound>[] = [
              { key: "round", header: "round", numeric: true },
              { key: "client", header: "client", numeric: true },
              { key: "status", header: "status", render: (x) => <StatusBadge s={x.status} /> },
              { key: "reason", header: "reason", render: (x) => (x.reason ? <span className="mono">{x.reason}</span> : <span className="muted">n/a</span>) },
              { key: "receipt_id", header: "receipt", render: (x) => (x.receipt_id ? <span className="mono">{x.receipt_id}</span> : <span className="muted">none</span>) },
              { key: "label", header: "label", render: (x) => <span style={{ whiteSpace: "normal" }}>{x.label ?? "n/a"}</span> },
            ];
            return (
              <>
                <DataTable columns={cols} rows={r.rounds} empty="The backend returned no rounds." />
                <SourceCaption source={r.source} />
              </>
            );
          }}
        </Async>
      </Card>

      <Async state={receipts} what="receipts">
        {(res) => (
          <>
            <Card title="Receipts" badge={<ReplayedBadge label="stored receipt files, verified without proving" />}>
              {res.receipts.length === 0 ? (
                <p className="muted">No receipt files found.</p>
              ) : (
                <div className="qs-grid" style={{ marginTop: 8 }}>
                  {res.receipts.map((r) => (
                    <ReceiptCard key={r.id} r={r} />
                  ))}
                </div>
              )}
              <SourceCaption source={res.source} />
            </Card>
            <Card title="Hardware that produced these proofs" source={res.hardware.source ?? res.source}>
              <dl className="qs-kv">
                {Object.entries(res.hardware)
                  .filter(([k]) => k !== "source")
                  .map(([k, v]) => (
                    <div key={k} style={{ display: "contents" }}>
                      <dt>{k}</dt>
                      <dd>{typeof v === "boolean" ? (v ? "yes" : "no") : String(v)}</dd>
                    </div>
                  ))}
              </dl>
            </Card>
          </>
        )}
      </Async>
    </>
  );
}

function ReceiptCard({ r }: { r: Receipt }) {
  return (
    <article className="qs-stat" style={{ padding: 14, display: "grid", gap: 8, alignContent: "start" }}>
      <ReplayedBadge label={r.label} />
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Verified v={r.verified} />
        <span className="mono">{r.id}</span>
      </div>
      <p style={{ margin: 0, fontSize: "0.88rem", fontWeight: 600 }}>{r.label}</p>
      <dl className="qs-kv">
        <dt>round / client</dt><dd>{r.round ?? "n/a"} / {r.client ?? "n/a"}</dd>
        <dt>generated (file mtime)</dt><dd>{r.generated}</dd>
        <dt>receipt size</dt><dd>{fmtBytes(r.bytes)}</dd>
        <dt>journal size</dt><dd>{fmtBytes(r.journal_bytes)}</dd>
        <dt>prove_s</dt><dd>{fmtNum(r.prove_s, 1)} s</dd>
        <dt>cycles</dt><dd>{fmtNum(r.cycles, 0)}</dd>
        <dt>peak memory</dt><dd>{fmtNum(r.peak_rss_mb, 0)} MB</dd>
        <dt>verify_s</dt><dd>{fmtNum(r.verify_s, 3)} s</dd>
        <dt>image id</dt><dd className="mono">{r.image_id ?? "n/a"}</dd>
        <dt>path</dt><dd className="mono">{r.path}</dd>
        {r.verify_error && (<><dt>verify error</dt><dd className="mono">{r.verify_error}</dd></>)}
      </dl>
    </article>
  );
}
