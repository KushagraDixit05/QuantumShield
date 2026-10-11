"use client";
import { Async, Card, DataTable, DivergedNote, EmptyState, type Column } from "@/components/shared";
import { getResults, getScenarios, useApi, type Row } from "@/lib/api";
import { seriesVar } from "@/lib/theme/palette";
import { CurvesChart, type Curve } from "./CurvesChart";
import { SummaryTable } from "./SummaryTable";

const isNumArray = (v: unknown): v is number[] => Array.isArray(v) && v.every((x) => typeof x === "number");

export function OverviewView() {
  const curves = useApi(() => getResults("scenarios_curves"));
  const summary = useApi(() => getResults("scenarios"));
  const scen = useApi(getScenarios);

  return (
    <>
      <Card title="Scenarios A / B / C">
        <Async state={curves} what="scenario curves">
          {(res) => {
            const sc = (res.json?.scenarios ?? null) as Record<string, unknown> | null;
            const list: Curve[] = [];
            ["A", "B", "C"].forEach((id, i) => {
              const v = sc?.[id];
              if (isNumArray(v)) {
                const meta = scen.data?.scenarios.find((s) => s.id === id);
                list.push({ id, label: meta ? meta.label : id, color: seriesVar(i), values: v });
              }
            });
            if (!list.length) return <EmptyState title="No A/B/C curves in the stored JSON" error={`source: ${res.source.join(", ")}`} />;
            const seed = res.json?.seed;
            const rounds = res.json?.rounds;
            return (
              <CurvesChart
                curves={list}
                source={res.source}
                subtitle={`One stored run${typeof seed === "number" ? `, seed ${seed}` : ""}${typeof rounds === "number" ? `, ${rounds} rounds` : ""}. Accuracy on the held-out test set.`}
              />
            );
          }}
        </Async>
        <Async state={scen} what="scenario definitions">
          {(s) => (
            <details className="qs-details">
              <summary>What A, B and C are</summary>
              <ul>
                {s.scenarios.map((x) => (
                  <li key={x.id}>
                    <b>{x.id}</b> ({x.attack} attack, defence {x.defence}): {x.description}
                  </li>
                ))}
              </ul>
              <p className="qs-source">Source: {s.source.join(", ")}</p>
            </details>
          )}
        </Async>
      </Card>

      <Card title="Summary across seeds">
        <Async state={summary} what="scenario summary">
          {(res) => {
            const cols: Column<Row>[] = res.columns.map((c) => ({ key: c, header: c.replace(/_/g, " ") }));
            return (
              <>
                {res.diverged_note && <DivergedNote text={res.diverged_note.text} />}
                <SummaryTable rows={res.rows} />
                <details className="qs-details">
                  <summary>Per-seed rows ({res.rows.length})</summary>
                  <DataTable columns={cols} rows={res.rows} />
                  <p className="muted">A stored final_acc of 0.0 together with a diverged_round means DIVERGED (D-012), not an accuracy.</p>
                </details>
                <p className="qs-source">Source: {res.source.join(", ")}</p>
              </>
            );
          }}
        </Async>
      </Card>
    </>
  );
}
