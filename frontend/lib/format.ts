export const fmtNum = (v: unknown, digits = 3): string =>
  typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("en-US", { maximumFractionDigits: digits }) : "n/a";
export const fmtAcc = (v: unknown): string => (typeof v === "number" ? v.toFixed(4) : "n/a");
export function fmtBytes(v: unknown): string {
  if (typeof v !== "number") return "n/a";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)} MB`;
  if (v >= 10_000) return `${(v / 1000).toFixed(1)} kB`;
  return `${v.toLocaleString("en-US")} B`;
}
