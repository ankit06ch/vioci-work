.PHONY: dev api fe test-web kill-dev-ports

# Free stuck dev servers (zombie uvicorn on :8000 causes signup to hang with no logs).
kill-dev-ports:
	@-kill -9 $$(lsof -t -i:8000) 2>/dev/null || true
	@-kill -9 $$(lsof -t -i:5173) 2>/dev/null || true
	@-kill -9 $$(lsof -t -i:5174) 2>/dev/null || true

# Local development: FastAPI on :8000 and Vite on :5173 (proxies /api and WS).
dev: kill-dev-ports
	@echo "Install deps: pip install -e '.[web,google,dev]' && cd webapp && npm install"
	trap 'kill 0' INT EXIT; \
	PYTHONPATH=. .venv/bin/uvicorn server.main:app --reload --host 127.0.0.1 --port 8000 & \
	cd webapp && npm run dev & \
	wait

api:
	PYTHONPATH=. .venv/bin/uvicorn server.main:app --reload --host 127.0.0.1 --port 8000

fe:
	cd webapp && npm run dev

test-web:
	PYTHONPATH=. .venv/bin/pytest tests/test_webapp_smoke.py -q
