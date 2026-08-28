# Makefile — Caissa development targets
#
# The venv lives in the main checkout (.venv), not in this worktree.  The path is
# resolved via git rev-parse --git-common-dir so it works correctly in any worktree.
# Override with PY=/path/to/python if needed.
#
# Usage:
#   make test         Fast unit + RPA tests (no Qt, no display)
#   make test-all     Full test run by path (cross-check that markers and filesystem agree)
#   make cov          Coverage gate for Code.Rpa (≥ 90 %, branch=true)
#   make test-ui      Integration tests (requires a running Caissa process)
#   make test-cv      CV/OCR tests (requires display + opencv + tesseract)
#   make lint         ruff check with Caissa-scoped config (D11)
#   make docs         Sphinx autodoc → docs/rpa/api/
#   make rpa-doctor   Print RPA capability probe and install hints
#   make help         Show this help

GIT_COMMON := $(shell git rev-parse --git-common-dir 2>/dev/null)
PY ?= $(GIT_COMMON)/../.venv/bin/python3

.PHONY: test test-all cov test-ui test-cv lint docs rpa-doctor help

test: ## Fast unit + RPA engine tests (no Qt, no display needed)
	QT_QPA_PLATFORM=offscreen $(PY) -m pytest -m "unit or rpa" -v

test-all: ## Full test run by path — cross-checks that markers and filesystem agree
	QT_QPA_PLATFORM=offscreen $(PY) -m pytest tests -v

cov: ## Coverage gate: ≥ 90 % branch coverage for Code.Rpa
	QT_QPA_PLATFORM=offscreen $(PY) -m pytest -m "unit or rpa" \
	  --cov=Code.Rpa \
	  --cov-fail-under=90 \
	  --cov-branch \
	  --cov-config=.coveragerc \
	  --cov-report=term-missing \
	  -v

test-ui: ## Integration tests — launches tools/caissa with CAISSA_TEST=1
	$(PY) -m pytest -m "ui or rpa_ui" -v

test-cv: ## CV/OCR tests — requires display + opencv + tesseract (opt-in)
	CAISSA_RPA_CV=1 $(PY) -m pytest -m rpa_cv -v

RUFF ?= $(shell which ruff 2>/dev/null || $(PY) -c "import shutil; print(shutil.which('ruff') or 'ruff')" 2>/dev/null)

lint: ## ruff check with Caissa-scoped config (--config required — D11)
	$(RUFF) check --config ruff.toml

docs: ## Sphinx autodoc → docs/rpa/api/ (zero warnings required)
	$(PY) -m sphinx -W --keep-going docs docs/rpa/api -b html

rpa-doctor: ## Print RPA capability probe (CV/OCR availability and install hints)
	$(PY) -c "\
import sys, os; \
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath('.')), 'bin')); \
print('RPA doctor: Vision/Availability not yet implemented (Phase 7)')"

help: ## Show available make targets
	@grep -E '^[a-zA-Z_-]+:.*## .*$$' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
