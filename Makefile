UV ?= uv
UV_RUN = $(UV) run --frozen

.PHONY: help sync lint test docs verify

help:
	@echo "sync   Sync the root development environment without updating submodules"
	@echo "lint   Check Python style and each shell script's syntax"
	@echo "test   Run hardware-free root tests (integration skips are reported)"
	@echo "docs   Check bilingual documentation, links and project routing"
	@echo "verify Run lint, documentation checks and tests"

sync:
	$(UV) sync --frozen

lint:
	$(UV_RUN) ruff check src tests scripts/check_docs.py
	$(UV_RUN) ruff format --check src tests scripts/check_docs.py
	@for script in scripts/*.sh; do bash -n "$$script" || exit $$?; done

test:
	$(UV_RUN) pytest

docs:
	$(UV_RUN) python scripts/check_docs.py

verify: lint docs test
