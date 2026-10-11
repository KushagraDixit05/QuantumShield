"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge, Card, DataTable, EmptyState, SourceCaption, type Column } from "@/components/shared";
import { ApiError, getConsensus, verifyCertificate, type CertificateVerifyResponse, type ConsensusRound, type ConsensusView as View } from "@/lib/api";

const KEY = "qs.lastRunId";
type VerifyState = { loading: boolean; res?: CertificateVerifyResponse; error?: string };

export function ConsensusView() {
  const [runId, setRunId] = useState("");
  const [input, setInput] = useState("");
  const [view, setView] = useState<View | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [remembered, setRemembered] = useState<string | null>(null);
  const [verif, setVerif] = useState<Record<number, VerifyState>>({});

  useEffect(() => {
    try {
      const v = sessionStorage.getItem(KEY);
      if (v) {
        // sessionStorage exists only on the client; reading it on mount is the intended sync.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setRemembered(v);
        setInput(v);
        void load(v);
      }
    } catch {
      /* storage blocked */
    }
  }, []);

  async function load(id: string) {
    const clean = id.trim();
    if (!clean) return;
    setRunId(clean);
    setLoading(true);
    setError(null);
    setView(null);
    setVerif({});
    try {
      setView(await getConsensus(clean));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function verify(round: number) {
    setVerif((v) => ({ ...v, [round]: { loading: true } }));
    try {
      const res = await verifyCertificate({ run_id: runId, round });
      setVerif((v) => ({ ...v, [round]: { loading: false, res } }));
    } catch (e) {
      const msg = e instanceof ApiError && e.status === 501 ? `Backend says: not implemented (HTTP 501). ${e.message}` : e instanceof Error ? e.message : String(e);
      setVerif((v) => ({ ...v, [round]: { loading: false, error: msg } }));
    }
  }

  return (
    <>
      <Card title="Pick a run">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void load(input);
          }}
          style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "end" }}
        >
          <label>Run id<br />
            <input value={input} onChange={(e) => setInput(e.target.value)} className="mono" style={{ width: "min(360px, 80vw)" }} placeholder="paste a run id" />
          </label>
          <button type="submit" className="qs-btn" disabled={!input.trim() || loading} style={{ fontWeight: 700, borderWidth: 2 }}>Load</button>
          {remembered && <button type="button" className="qs-btn" onClick={() => { setInput(remembered); void load(remembered); }}>Use latest run from this session ({remembered.slice(0, 8)})</button>}
        </form>
        {!remembered && <p className="muted" style={{ fontSize: "0.85rem" }}>No run started in this browser session yet. Start one on <Link href="/run">/run</Link> or paste an id.</p>}
      </Card>

      {loading && <p className="muted" role="status">Loading consensus view...</p>}
      {error && <EmptyState title="Consensus view unavailable" error={error} />}
      {view && <Body view={view} runId={runId} verif={verif} onVerify={verify} />}
    </>
  );
}

function short(h: string | null, n = 12) {
  return h ? (h.length > n ? `${h.slice(0, n)}...` : h) : "none";
}

function Body({ view, runId, verif, onVerify }: { view: View; runId: string; verif: Record<number, VerifyState>; onVerify: (r: number) => void }) {
  const src = `GET /api/consensus/${runId} (Node state of the backend runner)`;
  const cols: Column<ConsensusRound>[] = [
    { key: "round", header: "round", numeric: true },
    { key: "leader", header: "leader", render: () => <>node {view.leader}</> },
    { key: "votes", header: "votes (valid / total)", numeric: true, render: (r) => `${r.votes.filter((v) => v.valid).length} / ${r.votes.length}` },
    { key: "quorum", header: "quorum", numeric: true, render: () => view.quorum },
    { key: "finalized", header: "finalized", render: (r) => (r.finalized ? <Badge tone="good">&#10003; finalized</Badge> : <Badge tone="bad">&#10007; not finalized</Badge>) },
    { key: "equivocators", header: "equivocators", render: (r) => (r.equivocators.length ? r.equivocators.join(", ") : "none") },
    { key: "bad_votes", header: "bad votes", numeric: true },
  ];
  return (
    <>
      <Card title="Parameters">
        <div className="qs-stats">
          <div className="qs-stat"><b>{view.n}</b><span>nodes (n)</span></div>
          <div className="qs-stat"><b>{view.f}</b><span>tolerated faults (f)</span></div>
          <div className="qs-stat"><b>{view.quorum}</b><span>quorum (2f+1)</span></div>
          <div className="qs-stat"><b>node {view.leader}</b><span>{view.leader_policy}</span></div>
        </div>
        <SourceCaption source={src} />
      </Card>

      <Card title="Rounds">
        <DataTable columns={cols} rows={view.rounds} empty="No rounds recorded for this run yet." />
        <h3>View changes</h3>
        <div className="qs-note" role="note">
          {view.view_changes.length === 0 ? "None occurred. " : `${view.view_changes.length} recorded. `}
          {view.view_changes_note}. The leader is fixed, so there is nothing to plot here.
        </div>
        <SourceCaption source={src} />
      </Card>

      <Card title="Certificate chain">
        <p className="muted" style={{ marginTop: 0, fontSize: "0.88rem" }}>
          A certificate here is the round&apos;s set of signed votes; its id is a hash prefix of that vote set. Each round links to the model hash it certifies.
        </p>
        {view.rounds.length === 0 ? <p className="muted">No certificates yet.</p> : (
          <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 0 }}>
            {view.rounds.map((r, i) => {
              const v = verif[r.round];
              return (
                <li key={r.round} style={{ display: "grid", gridTemplateColumns: "24px minmax(0,1fr)", gap: 10 }}>
                  <div aria-hidden style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <span style={{ width: 12, height: 12, borderRadius: "50%", background: r.finalized ? "var(--ink)" : "transparent", border: "2px solid var(--ink)", marginTop: 6 }} />
                    {i < view.rounds.length - 1 && <span style={{ flex: 1, width: 2, background: "var(--axis)" }} />}
                  </div>
                  <div style={{ paddingBottom: 16, minWidth: 0 }}>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "baseline" }}>
                      <b>round {r.round}</b>
                      <span aria-hidden>&rarr;</span>
                      <span>certificate <code className="mono" title={r.certificate_id ?? ""}>{short(r.certificate_id)}</code></span>
                      <span aria-hidden>&rarr;</span>
                      <span>model <code className="mono" title={r.model_hash ?? undefined}>{short(r.model_hash, 16)}</code></span>
                      <button type="button" className="qs-btn" disabled={v?.loading} onClick={() => onVerify(r.round)}>
                        {v?.loading ? "Verifying..." : "Verify certificate (public keys only)"}
                      </button>
                    </div>
                    <details className="qs-details">
                      <summary>{r.votes.length} votes as recorded</summary>
                      <DataTable
                        columns={[
                          { key: "node", header: "node", numeric: true },
                          { key: "signer_alg", header: "signature algorithm" },
                          { key: "hash", header: "voted hash", render: (x) => <span className="mono">{short(x.hash, 16)}</span> },
                          { key: "valid", header: "valid at runtime", render: (x) => (x.valid ? "yes" : "no") },
                        ]}
                        rows={r.votes}
                      />
                    </details>
                    {v?.error && <div className="qs-note" role="alert">{v.error}</div>}
                    {v?.res && <VerifyResult res={v.res} />}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
        <SourceCaption source={src} />
      </Card>
    </>
  );
}

function VerifyResult({ res }: { res: CertificateVerifyResponse }) {
  return (
    <div className="qs-stat" style={{ marginTop: 8 }} role="status">
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {res.valid ? <Badge tone="good">&#10003; valid</Badge> : <Badge tone="bad">&#10007; not valid</Badge>}
        {res.quorum_met ? <Badge tone="good">quorum met</Badge> : <Badge tone="bad">quorum not met</Badge>}
      </div>
      <DataTable
        columns={[
          { key: "node", header: "node", numeric: true },
          { key: "ok", header: "vote", render: (c) => (c.ok ? <Badge tone="good">&#10003; ok</Badge> : <Badge tone="bad">&#10007; rejected</Badge>) },
          { key: "reason", header: "reason" },
        ]}
        rows={res.checked}
      />
      <p style={{ margin: "6px 0 0", fontSize: "0.85rem" }}>
        Checked with public keys only{res.public_keys_only ? "" : " (the backend did not confirm this)"}: no secret key is used by this check.
      </p>
      <SourceCaption source={res.source} />
    </div>
  );
}
