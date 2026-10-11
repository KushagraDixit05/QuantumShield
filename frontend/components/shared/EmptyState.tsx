import type { ReactNode } from "react";

export function EmptyState({ title, error, children }: { title: string; error?: string | null; children?: ReactNode }) {
  return (
    <div className="qs-empty" role="status">
      <b>{title}</b>
      {children}
      {error && <code>{error}</code>}
    </div>
  );
}
