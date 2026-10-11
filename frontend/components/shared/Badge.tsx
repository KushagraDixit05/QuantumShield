import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "good" | "warn" | "bad";

/** Small inline status badge. Always carries text (never colour alone). */
export function Badge({ tone = "neutral", children, title }: { tone?: BadgeTone; children: ReactNode; title?: string }) {
  return (
    <span className={`qs-badge ${tone}`} title={title}>
      {children}
    </span>
  );
}

/** Large, unmissable. Use for anything read from a stored receipt/file. ZK is ALWAYS replayed. */
export function ReplayedBadge({ label }: { label?: string }) {
  return (
    <span className="qs-bigbadge replayed" role="note">
      <b>REPLAYED</b>
      <small>{label ?? "read from a stored receipt or file; not computed now"}</small>
    </span>
  );
}

/** Large, unmissable. Only for values the backend computed in this session. */
export function LiveBadge({ label }: { label?: string }) {
  return (
    <span className="qs-bigbadge live" role="note">
      <b>LIVE</b>
      <small>{label ?? "computed now by the backend in this session"}</small>
    </span>
  );
}
