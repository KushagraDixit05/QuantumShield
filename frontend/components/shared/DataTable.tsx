import type { ReactNode } from "react";

export interface Column<R> {
  key: string;
  header: string;
  /** Right-align + tabular figures. */
  numeric?: boolean;
  render?: (row: R) => ReactNode;
}

export function DataTable<R extends object>({
  columns,
  rows,
  caption,
  empty = "No rows",
}: {
  columns: Column<R>[];
  rows: R[];
  caption?: string;
  empty?: string;
}) {
  if (!rows.length) return <p className="muted">{empty}</p>;
  return (
    <div className="qs-tablewrap">
      <table className="qs-table">
        {caption && <caption className="muted" style={{ textAlign: "left", fontSize: "0.8rem" }}>{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.numeric ? "num" : undefined} scope="col">
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? "num" : undefined}>
                  {c.render ? c.render(r) : cell((r as Record<string, unknown>)[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function cell(v: unknown): ReactNode {
  if (v === null || v === undefined || v === "") return <span className="muted">n/a</span>;
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("en-US") : v.toLocaleString("en-US", { maximumFractionDigits: 4 });
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}
