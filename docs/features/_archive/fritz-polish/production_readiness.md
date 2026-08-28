# Fritz Polish — Production Readiness (Gate E)

**Feature:** Caissa Fritz Polish  
**Phase:** 9 — Production Readiness  
**Date:** 2026-08-28  
**Status:** PASSED — all findings resolved

---

## Gate E Checklist

### 1. Correctness

- [x] Fritz unit suite: 130 passed, 0 failures (`pytest -m unit tests/unit/fritz/`)
- [x] Full unit + rpa suite: 429 passed, 0 Fritz failures (`make test`)
- [x] All xfail stubs for later phases remain as `strict=True` xfail placeholders
- [x] `tests/test_classical_invariant.py` green throughout all phases
- [x] `tests/test_ribbon_map.py` T-RMAP-01..08 all passing

### 2. Classical Invariant impact

- [x] No widget, toolbar entry, menu entry, or config key added to classical mode
- [x] All Fritz widgets are mode-gated; classical mode loads none of `bin/Code/Fritz/W*.py`
- [x] `resources/Modes/classical.json` unchanged
- [x] `tests/test_classical_invariant.py` passes on every phase branch

### 3. Non-functional

- [x] NFR-2: RST docstrings on all public and non-public callables in `Code.Fritz`
- [x] NFR-3: Complete type annotations with `from __future__ import annotations` throughout
- [x] NFR-7: No full-window pixel-comparison assertions
- [x] `make lint` zero issues for all `bin/Code/Fritz/**` and `tests/unit/fritz/**` modules

### 4. Architecture invariants

- [x] N-FRITZ-1: `Types.py` and `Errors.py` have zero third-party imports (enforced by `test_completeness.py`)
- [x] N-FRITZ-2: Only `WFritzPane.py`, `WFritzLCD.py`, `WRibbon.py`, `Ribbon.py`, `Delegates.py` import PySide6 (enforced by `test_completeness.py` AST check)
- [x] N-FRITZ-3: `EngineGateway.py` in adapter allowlist (reaches Qt-tainted upstream at runtime)
- [x] N-FRITZ-4: No `bin/Code/Fritz/` module imported from upstream Lucas Chess R6 code
- [x] Purity tiers declared in `feature_spec.md` §4 and enforced by `tests/unit/fritz/test_completeness.py`

### 5. Documentation

- [x] `docs/fritz/README.md` — index (Phase D)
- [x] `docs/fritz/concepts.md` — mental model (Phase D)
- [x] `docs/fritz/glossary.md` — 3-column term table (Phase D)
- [x] `docs/fritz/decisions.md` — ADR log D1..D11 (Phase D)
- [x] `docs/fritz/qss-contract.md` — E1-E4 `qproperty-` contract + per-widget tables (Phase 0)
- [x] `docs/fritz/ribbon.md` — ribbon JSON schema (Phase 7)
- [x] `docs/standards/ui-design-process.md` — design methodology (Phase 0)
- [x] `docs/standards/architecture.md` — purity-tier rules (Phase 0)
- [x] `make docs` clean — zero Sphinx warnings (resolved in Phase 9)

### 6. Test completeness

- [x] `test_every_planned_test_name_exists_in_suite` — all test names from `feature_steps.md` found
- [x] Every Fritz test declares exactly one suite marker as `pytestmark` at module level
- [x] Fritz branch coverage ≥ 90 % per `fritz.coveragerc` (`make cov-fritz`): **94.22 %**

### 7. Error handling

- [x] All new Fritz modules raise `FritzError` subclasses (`RibbonSpecError`, `QssContractError`, `PaneNotRegisteredError`)
- [x] `FritzError` inherits from `CaissaError` (from `Code.Rpa.Errors`)
- [x] All catch sites include `exc_info=True` where an exception is logged
- [x] `Ribbon.install` returns `None` on any failure — never a dead app

### 8. CI

**Decision:** CI is proposed but NOT added in this PR.

Rationale: Adding a GitHub Actions workflow is an outward-facing change that requires
explicit approval. Recommended next step: create `.github/workflows/fritz-unit.yml`
running `make test` and `make lint` on every push to `main` and every PR.

---

## Findings

### F1 — `RibbonModel.py` had zero branch coverage (RESOLVED — Phase 9)

`RibbonModel.py` was a pure module with no unit tests at all (0 % branch coverage).
Seventeen tests were written covering `load()` happy path, all `_validate()` error paths,
`all_slot_keys()`, `state()`, `overflow()`, `best_tab()`, and `compact()`.
See `tests/unit/fritz/test_ribbon_model.py`.

### F2 — `ModeGateway.py` had 54 % branch coverage (RESOLVED — Phase 9)

`active()`, `layout()`, `ribbon_name()`, `hook_module_name()`, and `_load()` error paths
were not exercised. Twelve new tests were added using monkeypatch injection of `_cache`
and `Code.path_resource`.
See `tests/unit/fritz/test_mode_gateway.py`.

### F3 — `ThemeGateway.py` had 58 % branch coverage (RESOLVED — Phase 9)

`nag_color()` cache-hit and ImportError fallback paths were untested.
Four new tests were added, including a `builtins.__import__` monkeypatch to simulate
`Code.Nags` unavailability, and an assertion that `invalidate()` resets `Nags.xdic_colors`.
See `tests/unit/fritz/test_theme_gateway.py`.

### F4 — `EvalModel.py` had 84 % branch coverage (RESOLVED — Phase 9)

Equal-position (`cp ≤ 25`), Black-better (`cp` −101 to −300), `describe(None)`,
`describe()` with empty `li_rm`, and `describe()` with a `mate` field were untested.
Five new tests were added.
See `tests/unit/fritz/test_eval_model.py`.

### F5 — `make docs` failed due to missing Sphinx and missing master document (RESOLVED — Phase 9)

`sphinx` and `sphinx-rtd-theme` were not installed in the development virtualenv.
Additionally, `docs/index.rst` (the Sphinx master document) did not exist.
Both were resolved: packages installed into `.venv`, minimal `docs/index.rst` created
with an empty toctree to satisfy `sphinx -W --keep-going`.

### F6 — Lint errors in new test files (RESOLVED — Phase 9)

New test files introduced seven `I001` (import order) and `F401` (unused import) lint
violations. All were auto-fixed with `ruff check --config ruff.toml --fix`.

---

## Archive

On completion of Phase 9, the `docs/features/fritz-polish/` directory should be
archived to `docs/features/_archive/fritz-polish/` with `git mv` so history follows.
The `**Status:**` front matter on each artefact becomes `Completed 2026-08-28`.
