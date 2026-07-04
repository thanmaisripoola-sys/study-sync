# StudySync Makefile

.PHONY: install playground run test clean

install:
	uv sync --link-mode=copy

playground:
	uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents

run:
	uv run uvicorn app.agent_runtime_app:agent_runtime --host 127.0.0.1 --port 8090

test:
	uv run pytest tests/

clean:
	rm -rf .venv __pycache__ .adk *.db .pytest_cache
