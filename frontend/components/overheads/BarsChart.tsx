"use client";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartFrame, DataTable, type Column } from "@/components/shared";
import { seriesVar } from "@/lib/theme/palette";
import type { Row } from "@/lib/api";

export interface BarSeries {
  key: string;
  label: string;
}

/** Grouped bars, one group per row (x category). Log scale optional (stated in the subtitle). */
export function BarsChart({
  title,
  subtitle,
  source,
  rows,
  xKey,
  series,
  unit,
  log = false,
}: {
  title: string;
  subtitle?: string;
  source: string;
  rows: Row[];
  xKey: string;
  series: BarSeries[];
  unit: string;
  log?: boolean;
}) {
  const cols: Column<Row>[] = [
    { key: xKey, header: xKey },
    ...series.map((s) => ({ key: s.key, header: `${s.label} (${unit})`, numeric: true })),
  ];
  return (
    <ChartFrame
      title={title}
      subtitle={`${subtitle ?? ""}${log ? " Log scale." : ""}`.trim() || undefined}
      source={source}
      legend={series.map((s, i) => ({ label: s.label, color: seriesVar(i) }))}
      table={<DataTable columns={cols} rows={rows} />}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey={xKey} stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} />
          <YAxis
            scale={log ? "log" : "linear"}
            domain={log ? [(min: number) => Math.max(min / 2, 1e-3), "auto"] : [0, "auto"]}
            allowDataOverflow={log}
            stroke="var(--axis)"
            tick={{ fill: "var(--muted)", fontSize: 12 }}
            width={56}
            label={{ value: unit, angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 12 }}
          />
          <Tooltip
            cursor={{ fill: "var(--grid)", opacity: 0.5 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <div className="qs-tip">
                  <div><b>{String(label)}</b></div>
                  {payload.map((p) => (
                    <div key={String(p.dataKey)}>
                      <span style={{ color: p.color }}>&#9632;</span> {p.name}: {Number(p.value).toLocaleString("en-US", { maximumFractionDigits: 4 })} {unit}
                    </div>
                  ))}
                </div>
              ) : null
            }
          />
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={seriesVar(i)} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
