VENV := .venv/bin

init:
	python3 -m venv .venv && $(VENV)/pip install -e ".[dev]"

test:
	$(VENV)/pytest

lint:
	$(VENV)/ruff check attendance tests && $(VENV)/mypy attendance

context-export:
	.venv/bin/python tools/export_context.py

ui:
	streamlit run attendance/ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
