"""Shared helpers: repo paths, CSV parsing, the D-012 text, the prover-lock probe."""
import csv
import fcntl
import re
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "demo" / "results"
LOCK_PATH = ROOT / ".zk_prove.lock"


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def parse_cell(v):
    """CSV cell -> int | float | None | str (blank cells are null; nothing is filled in)."""
    if v is None:
        return None
    s = v.strip()
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return v


def read_csv(path):
    """-> (columns, rows). Raises 404 `<repo-relative path> not found`."""
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, f"{rel_or_str(p)} not found")
    with open(p, newline="") as f:
        rd = csv.DictReader(f)
        rows = [{k: parse_cell(v) for k, v in r.items()} for r in rd]
        return list(rd.fieldnames or []), rows


rel_or_str = rel


def read_text(path):
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, f"{rel_or_str(p)} not found")
    return p.read_text()


def d012_note():
    """The D-012 text, parsed from docs/decisions.md (not retyped)."""
    for line in read_text(ROOT / "docs" / "decisions.md").splitlines():
        m = re.match(r"^- D-012\s+(.*)$", line)
        if m:
            return {"decision": "D-012", "text": m.group(1).strip()}
    raise HTTPException(404, "D-012 not found in docs/decisions.md")


def prover_lock_held():
    """True if another process holds an exclusive flock on .zk_prove.lock (non-blocking probe, released at once).
    The file is only opened for reading; this never creates it and never proves anything."""
    try:
        f = open(LOCK_PATH, "rb")
    except OSError:
        return False
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
        return False
    finally:
        f.close()
