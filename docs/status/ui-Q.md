# ui-Q status (QA)
Done: tests/e2e (package.json, playwright.config.ts, specs/), docs/screenshots (10 PNGs), docs/ui_report.md.
Results: pytest backend 86 passed; full suite minus tests/zk 234 passed; lint/typecheck/build clean; Playwright 31/32 passed (1 real defect: raw `**` markdown on /limitations).
Not run: tests/zk (needs prover). No source edited.
Needs: B1/F1 fix D-Q1; F1 D-Q3, D-Q4; F2 D-Q2; lead: add `cd tests/e2e && npm install` to ui-install. Details in docs/ui_report.md.
