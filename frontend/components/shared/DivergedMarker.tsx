export const D012_NOTE =
  "0.0 is a convention, not a measured accuracy: int64 overflow, recorded as 0.0 from the divergence round";

/** Replaces a number for a diverged run. Never render an accuracy next to it. */
export function DivergedMarker({ round, count, withNote = false }: { round?: number | null; count?: string; withNote?: boolean }) {
  return (
    <>
      <span className="qs-diverged" title={`D-012: ${D012_NOTE}`}>
        &#x2715; {count ? `DIVERGED ${count}` : round != null ? `DIVERGED at round ${round}` : "DIVERGED"}
      </span>
      {withNote && <DivergedNote />}
    </>
  );
}

export function DivergedNote({ text }: { text?: string }) {
  return (
    <p className="qs-note" role="note">
      <b>D-012.</b> {(text ?? D012_NOTE).replace(/\.+\s*$/, "")}.
    </p>
  );
}
