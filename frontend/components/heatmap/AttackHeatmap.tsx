"use client";
import { useMemo, useState } from "react";
import { Async, Badge, Card, DataTable, DivergedMarker, DivergedNote, SourceCaption, type Column } from "@/components/shared";
import { getLimitations, getResults, useApi, type Row } from "@/lib/api";
import { sequentialColor, sequentialNeedsLightText, SEQUENTIAL } from "@/lib/theme/palette";
import s from "./heatmap.module.css";

interface Cell {
  attack: string;
  defence: string;
  n: number;
  nDiv: number;
  mean: number | null;
  std: number | null;
  nAcc: number;
  rejected: number;
  seeds: number[];
}
const num = (v: unknown): number | null => (typeof v === "number" ? v : null);
const pct = (v: number | null) => (v === null ? "n/a" : `${(v * 100).toFixed(1)}%`);

function toCells(rows: Row[]): Cell[] {
  return rows.map((r) => ({
    attack: String(r.attack),
    defence: String(r.defence),
    n: num(r.n_seeds) ?? 0,
    nDiv: num(r.n_diverged) ?? 0,
    mean: num(r.mean_final_acc),
    std: num(r.std_final_acc),
    nAcc: num(r.n_accuracy_seeds) ?? 0,
    rejected: num(r.rejected_total) ?? 0,
    seeds: Array.isArray(r.seeds) ? (r.seeds as unknown as number[]) : [],
  }));
}
const plain = (t: string) => t.replace(/\*\*/g, "").replace(/`/g, "");
const uniq = (a: string[]) => a.filter((x, i) => a.indexOf(x) === i);

export function AttackHeatmap() {
  const matrix = useApi(() => getResults("attack_matrix"));
  return (
    <Async state={matrix} what="attack matrix">
      {(res) => <Matrix cells={toCells(res.rows)} source={res.source} note={res.diverged_note?.text} />}
    </Async>
  );
}

function Matrix({ cells, source, note }: { cells: Cell[]; source: string[]; note?: string }) {
  const limits = useApi(getLimitations);
  const [active, setActive] = useState<string | null>(null);
  const attacks = uniq(cells.map((c) => c.attack));
  const defences = uniq(cells.map((c) => c.defence));
  const get = (a: string, d: string) => cells.find((c) => c.attack === a && c.defence === d);
  const baseline = get("none", "off");
  const sel = active ? cells.find((c) => `${c.attack}|${c.defence}` === active) : undefined;
  const anyDiv = cells.some((c) => c.nDiv > 0);

  const flags = (c: Cell): string[] => {
    const f: string[] = [];
    if (c.attack !== "none" && c.rejected === 0) f.push("attack not stopped: 0 rejected");
    if (c.defence === "on" && c.nDiv > 0) f.push("defence on, still diverged");
    return f;
  };
  const delta = (c: Cell) => (c.mean !== null && baseline?.mean != null ? (c.mean - baseline.mean) * 100 : null);

  const replayNote = useMemo(() => {
    const items = limits.data?.sections.flatMap((x) => x.items) ?? [];
    const pick = (re: RegExp) => items.find((i) => re.test(i.text));
    return { replay: pick(/replay is rejected in both modes/i), div: pick(/divergence is recorded/i) };
  }, [limits.data]);

  const cols: Column<Cell>[] = [
    { key: "attack", header: "attack" },
    { key: "defence", header: "defence" },
    { key: "n", header: "seeds", numeric: true },
    { key: "mean", header: "mean final accuracy (non-diverged seeds)", numeric: true, render: (c) => (c.nDiv === c.n && c.n > 0 ? <DivergedMarker count={`${c.nDiv} of ${c.n}`} /> : pct(c.mean)) },
    { key: "std", header: "std (population, n)", numeric: true, render: (c) => pct(c.std) },
    { key: "nDiv", header: "diverged", render: (c) => (c.nDiv ? <DivergedMarker count={`${c.nDiv} of ${c.n}`} /> : `0 of ${c.n}`) },
    { key: "rejected", header: "rejected (all seeds, all rounds)", numeric: true },
    { key: "flags", header: "flags", render: (c) => flags(c).join("; ") || "none" },
  ];

  return (
    <>
      <Card title="Attack by defence: final accuracy" badge={<Badge tone="neutral">computed by backend from stored scenarios.csv</Badge>}>
        <p className="muted" style={{ marginTop: 0, fontSize: "0.88rem", maxWidth: "75ch" }}>
          Each cell is one attack/defence pairing over all its seeds: mean final test accuracy, its spread, how many seeds diverged and how many updates were
          rejected. Defence off is Ed25519 with plain aggregation; defence on is hybrid signatures plus the plaintext norm gate (not ZK).
        </p>
        <div className={s.grid} style={{ gridTemplateColumns: `minmax(64px, 0.45fr) repeat(${defences.length}, minmax(0, 1fr))` }} role="group" aria-label="Attack by defence matrix">
          <div />
          {defences.map((d) => (
            <div key={d} className={s.colhead}>defence {d}</div>
          ))}
          {attacks.map((a) => (
            <Row key={a} a={a} defences={defences} get={get} active={active} setActive={setActive} flags={flags} delta={delta} />
          ))}
        </div>

        <div className={s.scale} aria-label="Legend">
          <span>Accuracy scale:</span>
          <span>0%</span>
          {SEQUENTIAL.map((c) => <i key={c} className={s.swatch} style={{ background: c }} />)}
          <span>100%</span>
          <span style={{ marginLeft: 12 }}><i className={`${s.swatch} qs-diverged-fill`} /> diverged (not on the scale)</span>
          <span><b>FLAG</b> = attack not stopped (0 rejected) or defence on yet diverged</span>
        </div>
        <p className="muted" style={{ fontSize: "0.8rem", marginBottom: 0 }}>Delta compares each cell&apos;s mean with the benign cell (attack none, defence off) in percentage points. Colour is never the only carrier: every cell prints its values.</p>

        <div className={s.detail} aria-live="polite">
          {sel ? <Detail c={sel} flags={flags(sel)} delta={delta(sel)} /> : <span className="muted">Hover or focus a cell (arrow keys are not needed: tab between cells) to see its details.</span>}
        </div>

        <details className="qs-details">
          <summary>Table view</summary>
          <DataTable columns={cols} rows={cells} />
        </details>
        <SourceCaption source={source} />
      </Card>

      {(anyDiv || replayNote.div) && (
        <DivergedNote text={replayNote.div ? `${note ?? ""} Limitation ${replayNote.div.n}: ${plain(replayNote.div.text)}` : note} />
      )}
      {replayNote.replay && (
        <p className="qs-note" role="note">
          <b>Replay row (limitation {replayNote.replay.n}).</b> {plain(replayNote.replay.text)}
        </p>
      )}
      <SourceCaption source={limits.data?.source ?? "docs/limitations.md (via /api/limitations)"} />
    </>
  );
}

function Row({ a, defences, get, active, setActive, flags, delta }: {
  a: string; defences: string[]; get: (a: string, d: string) => Cell | undefined; active: string | null;
  setActive: (k: string | null) => void; flags: (c: Cell) => string[]; delta: (c: Cell) => number | null;
}) {
  return (
    <>
      <div className={s.rowhead}>attack {a}</div>
      {defences.map((d) => {
        const c = get(a, d);
        if (!c) return <div key={d} className="muted">no data</div>;
        const key = `${a}|${d}`;
        const diverged = c.nDiv > 0;
        const t = c.mean ?? 0;
        const style = diverged ? undefined : { background: sequentialColor(t), color: sequentialNeedsLightText(t) ? "#fff" : "#0b0b0b" };
        const dl = delta(c);
        const f = flags(c);
        return (
          <button
            key={d}
            type="button"
            aria-pressed={active === key}
            className={`${s.cell} ${diverged ? "qs-diverged-fill" : ""}`}
            style={style}
            onMouseEnter={() => setActive(key)}
            onFocus={() => setActive(key)}
            onClick={() => setActive(key)}
            aria-label={`attack ${a}, defence ${d}: ${c.nDiv === c.n ? "all seeds diverged" : `mean accuracy ${pct(c.mean)}`}, ${c.n} seeds, diverged ${c.nDiv} of ${c.n}, ${c.rejected} rejected${f.length ? `. ${f.join(", ")}` : ""}`}
          >
            {c.nDiv === c.n ? <DivergedMarker count={`${c.nDiv} of ${c.n}`} /> : <span className={s.big}>{pct(c.mean)}</span>}
            {c.nDiv > 0 && c.nDiv < c.n && <span className={s.line}><DivergedMarker count={`${c.nDiv} of ${c.n}`} /> <br />mean of the other {c.nAcc}: {pct(c.mean)}</span>}
            {c.nDiv === 0 && <span className={s.line}>&plusmn; {pct(c.std)} over {c.n} seeds</span>}
            <span className={s.line}>rejected: {c.rejected}</span>
            {dl !== null && !(a === "none" && d === "off") && <span className={s.line}>vs benign: {dl >= 0 ? "+" : ""}{dl.toFixed(1)} pts</span>}
            {f.map((x) => <span key={x} className={s.flag}>FLAG {x}</span>)}
          </button>
        );
      })}
    </>
  );
}

function Detail({ c, flags, delta }: { c: Cell; flags: string[]; delta: number | null }) {
  return (
    <dl className="qs-kv">
      <dt>cell</dt><dd>attack {c.attack}, defence {c.defence}</dd>
      <dt>seeds</dt><dd>{c.n} ({c.seeds.join(", ") || "n/a"})</dd>
      <dt>diverged</dt><dd>{c.nDiv ? <DivergedMarker count={`${c.nDiv} of ${c.n}`} /> : `0 of ${c.n}`}</dd>
      <dt>mean final accuracy</dt><dd>{c.mean === null ? "n/a (every seed diverged)" : `${pct(c.mean)} over ${c.nAcc} non-diverged seeds, std ${pct(c.std)}`}</dd>
      <dt>rejected</dt><dd>{c.rejected} updates across all seeds and rounds</dd>
      <dt>vs benign</dt><dd>{delta === null ? "n/a" : `${delta >= 0 ? "+" : ""}${delta.toFixed(1)} percentage points`}</dd>
      <dt>flags</dt><dd>{flags.join("; ") || "none"}</dd>
    </dl>
  );
}
