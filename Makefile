UV ?= uv
UV_RUN = $(UV) run --frozen

.PHONY: help sync lint test docs verify

help:
	@echo "sync   Sync the root development environment without updating submodules"
	@echo "lint   Check Python style and each shell script's syntax"
	@echo "test   Run hardware-free root and contract tests (integration skips are reported)"
	@echo "docs   Check bilingual documentation, links and project routing"
	@echo "verify Run lint, documentation checks and tests"

sync:
	$(UV) sync --frozen

lint:
	$(UV_RUN) ruff check src tests scripts/check_docs.py third-party/agilex-contract
	$(UV_RUN) ruff format --check src tests scripts/check_docs.py third-party/agilex-contract
	@for script in scripts/*.sh; do bash -n "$$script" || exit $$?; done

test:
	$(UV_RUN) pytest tests third-party/agilex-contract/tests

docs:
	$(UV_RUN) python scripts/check_docs.py

verify: lint docs test
