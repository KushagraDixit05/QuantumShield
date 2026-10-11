.PHONY: api ui ui-build ui-gen ui-test ui-install setup test smoke baseline demo results sigbench forgery phase2 phase3 zk-build zk-crosscheck
PY ?= .venv/bin/python
setup:
	python3 -m venv .venv && $(PY) -m pip install -r requirements.txt
test:
	$(PY) -m pytest -q
smoke:
	$(PY) -m pytest -q tests/test_smoke.py
baseline:
	$(PY) -m experiments.run_baseline --config configs/baseline.yaml
demo:
	$(PY) -m demo.run_demo --all
	$(PY) -m demo.plot
	$(PY) -m demo.overheads
results: demo
sigbench:
	$(PY) -m pq.bench --config configs/phase2.yaml
forgery:
	$(PY) -m pq.forgery --config configs/phase2.yaml
phase2:
	$(PY) -m experiments.run_phase2 --config configs/phase2.yaml
phase3:
	$(PY) -m experiments.run_phase3 --config configs/phase3.yaml
zk-build:
	cd zk && cargo build --release
zk-crosscheck:
	$(PY) -m zk.crosscheck
api:
	$(PY) -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
# Regenerate docs/openapi.json and frontend/lib/api/schema.d.ts from the backend.
ui-gen:
	$(PY) -m backend.export_openapi
	cd frontend && npm run gen:api
ui-build:
	cd frontend && npm run build
# Backend (8000) and a production Next server (3000) together; Ctrl-C stops both. Always rebuilds: `make ui-test` leaves a build that points at :8011.
ui:
	@$(MAKE) ui-build
	@trap 'kill 0' INT TERM EXIT; \
	$(PY) -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 & \
	(cd frontend && npm run start -- -H 127.0.0.1 -p 3000) & \
	wait
# Backend tests, frontend lint/typecheck/build, then the headless-browser smoke test (tests/e2e). Never proves.
ui-test:
	$(PY) -m pytest tests/backend tests/hardening -q
	cd frontend && npm run check:api
	cd frontend && npm run lint && npm run typecheck && npm run build
	cd tests/e2e && npx playwright test
ui-install:
	cd frontend && npm install
	cd tests/e2e && npm install
