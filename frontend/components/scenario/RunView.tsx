"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Async, Badge, Card, ChartFrame, DivergedMarker, DivergedNote, EmptyState, LiveBadge, SourceCaption } from "@/components/shared";
import { createRun, getScenarios, streamRun, useApi, type Aggregator, type AttackName, type DefenceMode, type RunEvent, type RunRequest, type ScenarioId, type ScenariosResponse, type SeedDone } from "@/lib/api";
import { fmtAcc } from "@/lib/format";
import { seriesVar } from "@/lib/theme/palette";
import { RejectionLog } from "./RejectionLog";
import type { LogRow } from "./reasons";

type RoundEv = Extract<RunEvent, { type: "round" }>;
type Status = "idle" | "submitting" | "queued" | "running" | "done" | "error";

export const LAST_RUN_KEY = "qs.lastRunId";
function rememberRun(id: string) {
  try {
    sessionStorage.setItem(LAST_RUN_KEY, id);
  } catch {
    /* storage unavailable: the consensus page then asks for an id */
  }
}

export function RunView() {
  const scen = useApi(getScenarios);
  return (
    <Async state={scen} what="scenario definitions">
      {(s) => <Runner scen={s} />}
    </Async>
  );
}

function Runner({ scen }: { scen: ScenariosResponse }) {
  const [mode, setMode] = useState<"scenario" | "custom">("scenario");
  const [scenario, setScenario] = useState<ScenarioId>(scen.scenarios[0]?.id ?? "A");
  const [attackOn, setAttackOn] = useState(true);
  const [attack, setAttack] = useState<AttackName>("scaled");
  const [defence, setDefence] = useState<DefenceMode>("on");
  const [aggregator, setAggregator] = useState<Aggregator>("fedavg");
  const [seeds, setSeeds] = useState<number[]>(scen.default_seeds.slice(0, 5));
  const [rounds, setRounds] = useState<number>(scen.default_rounds);

  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [queuePos, setQueuePos] = useState<number | null>(null);
  const [started, setStarted] = useState<Extract<RunEvent, { type: "started" }>[]>([]);
  const [roundEvs, setRoundEvs] = useState<RoundEv[]>([]);
  const [seedDone, setSeedDone] = useState<SeedDone[]>([]);
  const [doneSource, setDoneSource] = useState<string | null>(null);
  const [countSeed, setCountSeed] = useState<number | null>(null);
  const close = useRef<(() => void) | null>(null);

  const stop = useCallback(() => {
    close.current?.();
    close.current = null;
  }, []);
  useEffect(() => stop, [stop]); // EventSource closed on unmount

  const pool = useMemo(() => Array.from(new Set([0, 1, 2, 3, 4, ...scen.default_seeds])).sort((a, b) => a - b), [scen.default_seeds]);
  const toggleSeed = (n: number) =>
    setSeeds((cur) => (cur.includes(n) ? cur.filter((x) => x !== n) : cur.length >= 5 ? cur : [...cur, n].sort((a, b) => a - b)));

  const onEvent = useCallback((ev: RunEvent) => {
    switch (ev.type) {
      case "queued":
        setStatus("queued");
        setQueuePos(ev.position);
        break;
      case "started":
        setStatus("running");
        setStarted((c) => [...c, ev]);
        break;
      case "round":
        setStatus("running");
        setRoundEvs((c) => [...c, ev]);
        break;
      case "seed_done":
        setSeedDone((c) => [...c, ev]);
        break;
      case "done":
        setStatus("done");
        setSeedDone(ev.results);
        setDoneSource(ev.source);
        break;
      case "error":
        setStatus("error");
        setError(ev.message);
        break;
    }
  }, []);

  function buildRequest(): RunRequest {
    // live_zk is never sent: there is no live ZK control (the backend rejects it anyway).
    const base = { aggregator, seeds, rounds };
    if (mode === "scenario") {
      const meta = scen.scenarios.find((x) => x.id === scenario);
      if (attackOn || !meta) return { ...base, scenario };
      return { ...base, attack: "none", defence: meta.defence };
    }
    return { ...base, attack: attackOn ? attack : "none", defence };
  }

  async function run() {
    stop();
    setError(null);
    setStarted([]);
    setRoundEvs([]);
    setSeedDone([]);
    setDoneSource(null);
    setRunId(null);
    setQueuePos(null);
    setCountSeed(null);
    setStatus("submitting");
    try {
      const created = await createRun(buildRequest());
      setRunId(created.id);
      setQueuePos(created.queue_position);
      rememberRun(created.id);
      setStatus("queued");
      close.current = streamRun(created.id, onEvent, (m) => {
        setStatus((s) => (s === "done" || s === "error" ? s : "error"));
        setError((e) => e ?? m);
      });
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const busy = status === "submitting" || status === "queued" || status === "running";
  const cfg = started[0];
  const seedList = useMemo(() => Array.from(new Set(roundEvs.map((r) => r.seed))).sort((a, b) => a - b), [roundEvs]);
  const activeCountSeed = countSeed !== null && seedList.includes(countSeed) ? countSeed : (seedList[0] ?? null);

  const accData = useMemo(() => {
    const by = new Map<number, Record<string, number | null>>();
    for (const r of roundEvs) {
      const row = by.get(r.round) ?? { round: r.round };
      row[`s${r.seed}`] = r.diverged || r.accuracy === null ? null : r.accuracy;
      by.set(r.round, row);
    }
    return [...by.values()].sort((a, b) => (a.round as number) - (b.round as number));
  }, [roundEvs]);
  const divergedAt = useMemo(() => {
    const m = new Map<number, number>();
    for (const r of roundEvs) if (r.diverged && !m.has(r.seed)) m.set(r.seed, r.round);
    return m;
  }, [roundEvs]);
  const countData = useMemo(
    () =>
      roundEvs
        .filter((r) => r.seed === activeCountSeed)
        .map((r) => ({ round: r.round, accepted: r.diverged ? null : r.accepted_count, rejected: r.diverged ? null : r.rejected_count, finalized: r.consensus.finalized, diverged: r.diverged }))
        .sort((a, b) => a.round - b.round),
    [roundEvs, activeCountSeed],
  );
  const logRows: LogRow[] = useMemo(() => roundEvs.flatMap((r) => r.rejections.map((x) => ({ ...x, seed: r.seed }))), [roundEvs]);
  const maxRound = rounds - 1;

  return (
    <>
      <Card title="Configure a run" badge={<Badge tone="neutral">ZK: replay only</Badge>}>
        <p className="muted" style={{ marginTop: 0, fontSize: "0.88rem" }}>
          There is no live zero-knowledge proving on this page or on this server: updates are checked by signatures and the plaintext norm gate.
          Proof results exist only as stored receipts on the ZK page.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!busy && seeds.length) void run();
          }}
          style={{ display: "grid", gap: 16 }}
        >
          <fieldset style={fs}>
            <legend>Scenario</legend>
            <label><input type="radio" name="mode" checked={mode === "scenario"} onChange={() => setMode("scenario")} /> Preset A / B / C</label>{" "}
            <label><input type="radio" name="mode" checked={mode === "custom"} onChange={() => setMode("custom")} /> Custom attack and defence</label>
            {mode === "scenario" ? (
              <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                {scen.scenarios.map((x) => (
                  <label key={x.id} style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                    <input type="radio" name="scenario" checked={scenario === x.id} onChange={() => setScenario(x.id)} />
                    <span><b>{x.label}</b> <span className="muted">(attack {x.attack}, defence {x.defence}). {x.description}</span></span>
                  </label>
                ))}
              </div>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginTop: 8 }}>
                <label>Attack{" "}
                  <select aria-label="Attack" value={attack} onChange={(e) => setAttack(e.target.value as AttackName)}>
                    {scen.attacks.filter((a) => a !== "none").map((a) => <option key={a}>{a}</option>)}
                  </select>
                </label>
                <label>Defence{" "}
                  <select aria-label="Defence" value={defence} onChange={(e) => setDefence(e.target.value as DefenceMode)}>
                    <option value="off">off (Ed25519 + plain aggregation)</option>
                    <option value="on">on (hybrid signatures + plaintext norm gate)</option>
                  </select>
                </label>
              </div>
            )}
            <label style={{ display: "block", marginTop: 10 }}>
              <input type="checkbox" checked={attackOn} onChange={(e) => setAttackOn(e.target.checked)} /> Attack enabled{" "}
              <span className="muted">(off sends attack = none{mode === "scenario" ? ", keeping the preset's defence setting" : ""})</span>
            </label>
          </fieldset>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
            <fieldset style={fs}>
              <legend>Seeds (1 to 5)</legend>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {pool.map((n) => (
                  <label key={n}><input type="checkbox" checked={seeds.includes(n)} onChange={() => toggleSeed(n)} /> {n}</label>
                ))}
              </div>
              {!seeds.length && <div className="qs-note" role="alert">Select at least one seed.</div>}
            </fieldset>
            <label>Aggregator<br />
              <select aria-label="Aggregator" value={aggregator} onChange={(e) => setAggregator(e.target.value as Aggregator)}>
                {scen.aggregators.map((a) => <option key={a}>{a}</option>)}
              </select>
            </label>
            <label>Rounds (1 to 50)<br />
              <input type="number" min={1} max={50} value={rounds} onChange={(e) => setRounds(Math.min(50, Math.max(1, Number(e.target.value) || 1)))} style={{ width: 80 }} />
            </label>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <button type="submit" className="qs-btn" disabled={busy || !seeds.length} style={{ fontWeight: 700, borderWidth: 2, padding: "8px 20px" }}>
              {busy ? "Running..." : "Run"}
            </button>
            {busy && (
              <button type="button" className="qs-btn" onClick={() => { stop(); setStatus("idle"); }}>
                Stop watching
              </button>
            )}
            <span role="status" aria-live="polite" style={{ fontSize: "0.88rem" }}>
              <StatusText status={status} queuePos={queuePos} />
            </span>
          </div>
          {busy && <p className="muted" style={{ margin: 0, fontSize: "0.8rem" }}>There is no cancel endpoint: stopping closes this stream only; the backend finishes the queued run.</p>}
        </form>
        <SourceCaption source={scen.source} />
      </Card>

      {status === "error" && <EmptyState title="Run failed or the stream was lost" error={error} />}

      {(roundEvs.length > 0 || status === "running" || status === "done") && (
        <Card title="Live output" badge={<LiveBadge label="computed now by backend.runner for this run" />}>
          {cfg && (
            <p className="muted" style={{ marginTop: 0, fontSize: "0.88rem" }}>
              attack <b>{cfg.attack}</b>, defence <b>{cfg.defence}</b>, aggregator <b>{cfg.aggregator}</b>, {cfg.rounds} rounds, seeds {started.map((s) => s.seed).join(", ")}
              {runId && <> . run id <code className="mono">{runId}</code> . <Link href="/consensus">consensus view</Link></>}
            </p>
          )}
          {accData.length > 0 ? (
            <ChartFrame
              title="Test accuracy per round, one line per seed"
              subtitle="Accuracy on the held-out test set. A diverged round has no accuracy: the line stops and is marked, it is never drawn as 0."
              source={doneSource ?? "run event stream (computed live by backend.runner)"}
              legend={seedList.map((s, i) => ({ label: `seed ${s}`, color: seriesVar(i) }))}
              height={320}
              table={
                <div className="qs-tablewrap">
                  <table className="qs-table">
                    <thead><tr><th>round</th>{seedList.map((s) => <th key={s} className="num">seed {s}</th>)}</tr></thead>
                    <tbody>
                      {accData.map((p) => (
                        <tr key={p.round as number}>
                          <td>{p.round}</td>
                          {seedList.map((s) => {
                            const v = p[`s${s}`];
                            return <td key={s} className="num">{v === undefined ? <span className="muted">pending</span> : v === null ? <DivergedMarker /> : fmtAcc(v)}</td>;
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              }
            >
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={accData} margin={{ top: 10, right: 16, bottom: 20, left: 0 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="round" type="number" domain={[0, maxRound]} allowDecimals={false} stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} label={{ value: "round", position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 12 }} />
                  <YAxis domain={[0, 1]} stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} width={44} />
                  {[...divergedAt.entries()].map(([s, r]) => (
                    <ReferenceLine key={s} x={r} stroke="var(--ink-2)" strokeDasharray="5 4" label={{ value: `seed ${s} DIVERGED`, position: "insideTopRight", fill: "var(--ink)", fontSize: 12, fontWeight: 700 }} />
                  ))}
                  <Tooltip
                    content={({ active, label }) => {
                      if (!active) return null;
                      const p = accData.find((d) => d.round === label);
                      if (!p) return null;
                      return (
                        <div className="qs-tip">
                          <div><b>round {label}</b></div>
                          {seedList.map((s, i) => (
                            <div key={s} style={{ color: "var(--ink-2)" }}>
                              <span style={{ color: seriesVar(i) }}>&#9632;</span> seed {s}: {p[`s${s}`] === undefined ? "pending" : p[`s${s}`] === null ? "DIVERGED (no accuracy)" : fmtAcc(p[`s${s}`])}
                            </div>
                          ))}
                        </div>
                      );
                    }}
                  />
                  {seedList.map((s, i) => (
                    <Line key={s} type="monotone" dataKey={`s${s}`} stroke={seriesVar(i)} strokeWidth={2} dot={{ r: 3, strokeWidth: 2, stroke: "var(--surface)" }} connectNulls={false} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </ChartFrame>
          ) : (
            <p className="muted" role="status">Waiting for the first round...</p>
          )}
          {divergedAt.size > 0 && (
            <DivergedNote
              text={`${[...divergedAt.entries()].map(([s, r]) => `seed ${s} diverged at round ${r}`).join("; ")}. ${seedDone.find((d) => d.convention_note)?.convention_note ?? "0.0 is a convention, not a measured accuracy: int64 overflow, recorded as 0.0 from the divergence round"}`}
            />
          )}

          {countData.length > 0 && (
            <ChartFrame
              title="Accepted and rejected updates per round"
              subtitle={
                <>
                  Seed{" "}
                  <select value={activeCountSeed ?? ""} onChange={(e) => setCountSeed(Number(e.target.value))} aria-label="Seed for the counts chart">
                    {seedList.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </>
              }
              source="run event stream (accepted_count, rejected_count)"
              legend={[{ label: "accepted", color: seriesVar(0) }, { label: "rejected", color: seriesVar(1) }]}
              height={240}
              table={
                <div className="qs-tablewrap">
                  <table className="qs-table">
                    <thead><tr><th>round</th><th className="num">accepted</th><th className="num">rejected</th><th>finalized</th></tr></thead>
                    <tbody>{countData.map((c) => <tr key={c.round}><td>{c.round}</td><td className="num">{c.accepted ?? "n/a"}</td><td className="num">{c.rejected ?? "n/a"}</td><td>{c.diverged ? "diverged (no round ran)" : c.finalized ? "yes" : "no"}</td></tr>)}</tbody>
                  </table>
                </div>
              }
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={countData} margin={{ top: 10, right: 16, bottom: 20, left: 0 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="round" stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} label={{ value: "round", position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 12 }} />
                  <YAxis allowDecimals={false} stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} width={32} />
                  <Tooltip cursor={{ fill: "var(--grid)", opacity: 0.4 }} contentStyle={{ background: "var(--surface)", border: "1px solid var(--axis)", color: "var(--ink)" }} />
                  <Bar dataKey="accepted" stackId="c" fill={seriesVar(0)} stroke="var(--surface)" strokeWidth={2} isAnimationActive={false} />
                  <Bar dataKey="rejected" stackId="c" fill={seriesVar(1)} stroke="var(--surface)" strokeWidth={2} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </ChartFrame>
          )}

          {seedDone.length > 0 && (
            <div className="qs-tablewrap" style={{ marginTop: 12 }}>
              <table className="qs-table">
                <caption className="muted" style={{ textAlign: "left", fontSize: "0.8rem" }}>Per-seed result</caption>
                <thead><tr><th>seed</th><th className="num">final accuracy</th><th>divergence</th></tr></thead>
                <tbody>
                  {seedDone.map((d) => (
                    <tr key={d.seed}>
                      <td>{d.seed}</td>
                      <td className="num">{d.diverged_round !== null ? <DivergedMarker round={d.diverged_round} /> : fmtAcc(d.final_accuracy)}</td>
                      <td>{d.diverged_round !== null ? `from round ${d.diverged_round}` : "none"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <SourceCaption source={doneSource ?? "computed live by backend.runner (mirrors demo/run_demo.py:run_scenario)"} />
        </Card>
      )}

      <RejectionLog live={logRows} />
    </>
  );
}

const fs: React.CSSProperties = { border: "1px solid var(--rule)", padding: "10px 14px", margin: 0, minWidth: 0 };

function StatusText({ status, queuePos }: { status: Status; queuePos: number | null }) {
  switch (status) {
    case "idle": return <span className="muted">Ready.</span>;
    case "submitting": return <>Submitting...</>;
    case "queued": return <>Queued{queuePos !== null ? ` (position ${queuePos})` : ""}. Runs execute one at a time and wait while a prover lock is held.</>;
    case "running": return <>Running, streaming rounds.</>;
    case "done": return <Badge tone="good">done</Badge>;
    case "error": return <Badge tone="bad">error</Badge>;
  }
}
