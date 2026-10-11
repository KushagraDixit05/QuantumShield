import type { ReactNode } from "react";
import { SourceCaption } from "./SourceCaption";

export interface LegendItem {
  label: string;
  color: string;
}

/**
 * Wraps a chart: title, one-line takeaway, legend (>= 2 series), the chart (give it a fixed height),
 * an optional table view (`table`) for accessibility, and the mandatory Source caption.
 */
export function ChartFrame({
  title,
  subtitle,
  source,
  legend,
  table,
  height = 300,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  source: string | string[] | null | undefined;
  legend?: LegendItem[];
  table?: ReactNode;
  height?: number;
  children: ReactNode;
}) {
  return (
    <figure style={{ margin: "16px 0 0" }}>
      <figcaption>
        <h3 style={{ margin: 0 }}>{title}</h3>
        {subtitle && <div className="muted" style={{ fontSize: "0.85rem" }}>{subtitle}</div>}
      </figcaption>
      {legend && legend.length > 1 && (
        <div className="qs-legend" style={{ marginTop: 8 }}>
          {legend.map((l) => (
            <span key={l.label}>
              <i style={{ background: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
      )}
      <div className="qs-chart" style={{ height }}>
        {children}
      </div>
      {table && (
        <details className="qs-details">
          <summary>Table view</summary>
          {table}
        </details>
      )}
      <SourceCaption source={source} />
    </figure>
  );
}
