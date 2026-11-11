VENV := .venv/bin

init:
	python3 -m venv .venv && $(VENV)/pip install -e ".[dev]"

test:
	$(VENV)/pytest

lint:
	$(VENV)/ruff check attendance tests && $(VENV)/mypy attendance
