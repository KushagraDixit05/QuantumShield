"""python -m backend.export_openapi  ->  docs/openapi.json"""
import json

from .common import ROOT
from .main import app


def main():
    out = ROOT / "docs" / "openapi.json"
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
