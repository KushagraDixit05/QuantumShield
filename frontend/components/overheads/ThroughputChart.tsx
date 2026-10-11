"use client";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartFrame, DataTable } from "@/components/shared";
import { seriesVar } from "@/lib/theme/palette";
import type { Row } from "@/lib/api";

export function ThroughputChart({ rows, source }: { rows: Row[]; source: string }) {
  const configs = [...new Set(rows.map((r) => String(r.config)))];
  const clients = [...new Set(rows.map((r) => Number(r.clients)))].sort((a, b) => a - b);
  const data = clients.map((c) => {
    const p: Record<string, number | null> = { clients: c };
    for (const cfg of configs) {
      const r = rows.find((x) => String(x.config) === cfg && Number(x.clients) === c);
      p[cfg] = typeof r?.envelopes_per_s === "number" ? r.envelopes_per_s : null;
    }
    return p;
  });
  return (
    <ChartFrame
      title="Verification throughput"
      subtitle="Envelopes verified per second at a given number of clients per batch."
      source={source}
      legend={configs.map((c, i) => ({ label: c, color: seriesVar(i) }))}
      table={<DataTable columns={rows[0] ? Object.keys(rows[0]).map((k) => ({ key: k, header: k.replace(/_/g, " "), numeric: k !== "config" })) : []} rows={rows} />}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 20, left: 4 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="clients" stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} label={{ value: "clients per batch", position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 12 }} />
          <YAxis stroke="var(--axis)" tick={{ fill: "var(--muted)", fontSize: 12 }} width={56} />
          <Tooltip
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <div className="qs-tip">
                  <div><b>{String(label)} clients</b></div>
                  {payload.map((p) => (
                    <div key={String(p.dataKey)}><span style={{ color: p.color }}>&#9632;</span> {p.name}: {Number(p.value).toLocaleString("en-US", { maximumFractionDigits: 0 })} /s</div>
                  ))}
                </div>
              ) : null
            }
          />
          {configs.map((c, i) => (
            <Line key={c} dataKey={c} stroke={seriesVar(i)} strokeWidth={2} dot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2, fill: seriesVar(i) }} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
