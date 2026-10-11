"use client";
import { Async, Card } from "@/components/shared";
import { getLimitations, useApi } from "@/lib/api";

/** The source file marks emphasis with **...**; render it, never show the asterisks. */
function renderBold(text: string) {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? <b key={i}>{part}</b> : part));
}

export function LimitationsView() {
  const s = useApi(getLimitations);
  return (
    <Async state={s} what="limitations">
      {(l) => (
        <>
          {l.sections.map((sec) => (
            <Card key={sec.title} title={sec.title}>
              <ol className="qs-limits" start={sec.items[0]?.n} style={{ paddingLeft: 24 }}>
                {sec.items.map((it) => (
                  <li key={it.n} value={it.n}>{renderBold(it.text)}</li>
                ))}
              </ol>
            </Card>
          ))}
          <p className="qs-source">Source: {l.source}</p>
        </>
      )}
    </Async>
  );
}
