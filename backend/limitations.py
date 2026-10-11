"""Parse docs/limitations.md: '## ' headings and numbered items."""
import re

from .common import ROOT, read_text

SOURCE = "docs/limitations.md"


def parse(text):
    sections, cur = [], None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = {"title": line[3:].strip(), "items": []}
            sections.append(cur)
            continue
        m = re.match(r"^(\d+)\.\s+(.*\S)\s*$", line)
        if m and cur is not None:
            cur["items"].append({"n": int(m.group(1)), "text": m.group(2)})
    return sections


def load():
    return {"source": SOURCE, "sections": parse(read_text(ROOT / SOURCE))}
