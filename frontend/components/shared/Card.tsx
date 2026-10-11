import type { ReactNode } from "react";
import { SourceCaption } from "./SourceCaption";

export function Card({
  title,
  badge,
  source,
  children,
}: {
  title?: string;
  badge?: ReactNode;
  /** When given, a "Source:" caption is rendered at the bottom. */
  source?: string | string[] | null;
  children: ReactNode;
}) {
  return (
    <section className="qs-card">
      {(title || badge) && (
        <div className="qs-card-head">
          {title && <h2>{title}</h2>}
          {badge}
        </div>
      )}
      {children}
      {source !== undefined && <SourceCaption source={source} />}
    </section>
  );
}
