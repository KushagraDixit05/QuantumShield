/** "Source: <file>" caption. Pass the API's `source` field verbatim (string or string[]). */
export function SourceCaption({ source, note }: { source: string | string[] | null | undefined; note?: string }) {
  const list = Array.isArray(source) ? source : source ? [source] : [];
  return (
    <p className="qs-source">
      Source: {list.length ? list.join(", ") : "not reported by backend"}
      {note ? ` (${note})` : ""}
    </p>
  );
}
