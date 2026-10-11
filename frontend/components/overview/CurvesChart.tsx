"use client";
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartFrame, DivergedNote } from "@/components/shared";
import { fmtAcc } from "@/lib/format";

export interface Curve {
  id: string;
  label: string;
  color: string;
  values: number[];
}

/** Index of the first point of a trailing run of exact 0.0 values (D-012 convention), or null. */
export function divergedFrom(values: number[]): number | null {
  let i = values.length;
  while (i > 0 && values[i - 1] === 0) i--;
  return i < values.length && i > 0 ? i : null;
}

type Point = Record<string, number | null> & { round: number };

export function CurvesChart({ curves, source, subtitle }: { curves: Curve[]; source: string[]; subtitle: string }) {
  const len = Math.max(...curves.map((c) => c.values.length));
  const div = new Map(curves.map((c) => [c.id, divergedFrom(c.values)]));
  const data: Point[] = Array.from({ length: len }, (_, r) => {
    const p: Point = { round: r };
    for (const c of curves) {
      const d = div.get(c.id) ?? null;
      p[c.id] = d !== null && r >= d ? null : (c.values[r] ?? null);
    }
    return p;
  });
  const anyDiv = curves.filter((c) => div.get(c.id) != null);

  return (
    <>
      <ChartFrame
        title="Test accuracy per round"
        subtitle={subtitle}
        source={source}
        legend={curves.map((c) => ({ label: c.label, color: c.color }))}
        height={340}
        table={
          <div className="qs-tablewrap">
            <table className="qs-table">
              <thead>
                <tr>
                  <th>round</th>
                  {curves.map((c) => (
                    <th key={c.id} className="num">{c.id}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((p) => (
                  <tr key={p.round}>
                    <td>{p.round}</td>
                    {curves.map((c) => (
                      <td key={c.id} className="num">{p[c.id] === null ? "DIVERGED" : fmtAcc(p[c.id])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        }
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 16, bottom: 20, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="round" stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} label={{ value: "round (index in stored curve)", position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 12 }} />
            <YAxis domain={[0, 1]} stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} width={44} />
            {anyDiv.map((c) => {
              const d = div.get(c.id) as number;
              return (
                <ReferenceArea key={`a${c.id}`} x1={d} x2={len - 1} fill="var(--diverged)" fillOpacity={0.16} ifOverflow="visible" />
              );
            })}
            {anyDiv.map((c) => (
              <ReferenceLine
                key={`l${c.id}`}
                x={div.get(c.id) as number}
                stroke="var(--ink-2)"
                strokeDasharray="5 4"
                label={{ value: `${c.id} DIVERGED`, position: "insideTopRight", fill: "var(--ink)", fontSize: 12, fontWeight: 700 }}
              />
            ))}
            <Tooltip
              content={({ active, label }) => {
                if (!active || typeof label !== "number") return null;
                const p = data[label];
                return (
                  <div className="qs-tip">
                    <div><b>round {label}</b></div>
                    {curves.map((c) => (
                      <div key={c.id} style={{ color: "var(--ink-2)" }}>
                        <span style={{ color: c.color }}>&#9632;</span> {c.id}: {p[c.id] === null ? "DIVERGED (not an accuracy)" : fmtAcc(p[c.id])}
                      </div>
                    ))}
                  </div>
                );
              }}
            />
            {curves.map((c) => (
              <Line key={c.id} type="monotone" dataKey={c.id} stroke={c.color} strokeWidth={2} dot={{ r: 3, strokeWidth: 2, stroke: "var(--surface)", fill: c.color }} connectNulls={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </ChartFrame>
      {anyDiv.length > 0 && (
        <DivergedNote text="The stored curves contain 0.0 from the divergence round onward (shaded region, dashed line). 0.0 is a convention, not a measured accuracy: int64 overflow, recorded as 0.0 from the divergence round. Those points are not plotted as accuracy" />
      )}
    </>
  );
}
