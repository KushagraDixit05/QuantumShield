import type { ReactNode } from "react";

export function PageHeader({ kicker, title, children }: { kicker: string; title: string; children?: ReactNode }) {
  return (
    <header>
      <div className="qs-kicker">{kicker}</div>
      <h1>{title}</h1>
      {children && <p className="qs-lede">{children}</p>}
    </header>
  );
}
