import { DataTable, DivergedMarker, type Column } from "@/components/shared";
import { fmtAcc } from "@/lib/format";
import type { Row } from "@/lib/api";

interface Group {
  attack: string;
  defence: string;
  n: number;
  diverged: number;
  ok: number[];
  rejected: number;
}

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export function groupRows(rows: Row[]): Group[] {
  const m = new Map<string, Group>();
  for (const r of rows) {
    const key = `${r.attack}/${r.defence}`;
    const g = m.get(key) ?? { attack: String(r.attack), defence: String(r.defence), n: 0, diverged: 0, ok: [], rejected: 0 };
    g.n++;
    if (isNum(r.diverged_round)) g.diverged++;
    else if (isNum(r.final_acc)) g.ok.push(r.final_acc);
    if (isNum(r.rejected)) g.rejected += r.rejected;
    m.set(key, g);
  }
  return [...m.values()];
}

const mean = (a: number[]) => a.reduce((s, x) => s + x, 0) / a.length;
const sd = (a: number[]) => (a.length < 2 ? null : Math.sqrt(a.reduce((s, x) => s + (x - mean(a)) ** 2, 0) / a.length)); // population std, as in demo/results/scenarios_summary.md (np.std)

export function SummaryTable({ rows }: { rows: Row[] }) {
  const groups = groupRows(rows);
  const cols: Column<Group>[] = [
    { key: "attack", header: "attack" },
    { key: "defence", header: "defence" },
    { key: "n", header: "seeds", numeric: true },
    {
      key: "diverged",
      header: "diverged",
      numeric: true,
      render: (g) => (g.diverged ? <DivergedMarker count={`${g.diverged} of ${g.n}`} /> : "0"),
    },
    {
      key: "mean",
      header: "mean final acc",
      numeric: true,
      render: (g) =>
        g.ok.length === 0 ? <span className="muted">n/a (all diverged)</span> : (
          <>
            {fmtAcc(mean(g.ok))}
            {g.diverged > 0 && <span className="muted"> (over {g.ok.length} non-diverged)</span>}
          </>
        ),
    },
    { key: "sd", header: "std (population, n)", numeric: true, render: (g) => fmtAcc(sd(g.ok)) },
    { key: "rejected", header: "rejected updates", numeric: true },
  ];
  return <DataTable columns={cols} rows={groups} caption="Aggregated by the UI from the per-seed rows; diverged seeds are counted, never averaged in." />;
}
