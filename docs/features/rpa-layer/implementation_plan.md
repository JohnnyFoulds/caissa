# RPA Layer — Implementation Plan

**Spec reference:** [feature_spec.md](feature_spec.md)
**Phase tracker:** [feature_steps.md](feature_steps.md)

---

## Current State (as of 2026-08-28)

| What exists | Status |
|---|---|
| `docs/features/rpa-layer/` | Phase 0 in progress — documentation being written |
| `docs/rpa/` | Phase 0 in progress — design-time docs being written |
| `bin/Code/Rpa/` | Does not exist — Phase 1 will create it |
| `tests/unit/rpa/` | Does not exist — Phase 1 will create it |

Work begins at **Session 1-A** once Phase 0 PR is merged.

---

## How to use this plan

Each session maps to a small, coherent set of changes. The workflow for every session:

1. Run `make test` — confirm the session's target tests are **red** (failing or `xfail`).
2. Write the production code.
3. **Human diff review (Gate C)** — read every changed line before committing.
4. Run `make test` — all tests **green**, no regressions.
5. Run `make lint` — zero issues.
6. Update living docs if implementation revealed corrections.
7. Commit with the suggested message. More sessions in this phase? GOTO 1. Else open PR.

**One branch = one phase = one PR.** Never stack phases on one branch.

---

## Files to Create / Modify

| File | Action |
| --- | --- |
| `bin/Code/Rpa/__init__.py` | **Create** — 0 bytes, Phase 1 |
| `bin/Code/Rpa/Errors.py` | **Create** — Phase 1 |
| `bin/Code/Rpa/Types.py` | **Create** — Phase 1 |
| `bin/Code/Rpa/Driver.py` | **Create** — Phase 2 |
| `bin/Code/Rpa/Fakes.py` | **Create** — Phase 2 |
| `bin/Code/Rpa/Targets.py` | **Create** — Phase 3 |
| `bin/Code/Rpa/Resolve.py` | **Create** — Phase 3; **Edit** Phase 7 (add CV tiers) |
| `bin/Code/Rpa/AppState.py` | **Create** — Phase 4 |
| `bin/Code/Rpa/Journal.py` | **Create** — Phase 5 |
| `bin/Code/Rpa/Activities.py` | **Create** — Phase 5 |
| `bin/Code/Rpa/Runner.py` | **Create** — Phase 5 |
| `bin/Code/Rpa/Service.py` | **Create** — Phase 6 |
| `bin/Code/Rpa/Vision/` (5 files) | **Create** — Phase 7 |
| `bin/Code/Rpa/Workflows/` (6 files) | **Create** — Phase 8 |
| `bin/Code/Main/LogSetup.py` | **Create** — Phase 1 |
| `bin/Code/Debug/RemoteControl.py` | **Edit** — Phase 2 (extract to QtDriver); Phase 6 (add rpa_* handlers) |
| `tests/ui/rpa_client.py` | **Create** — Phase 6 |
| `tests/ui/rc_contract.json` | **Create** — Phase 2 (before any refactor) |
| `tests/ui/test_rc_contract.py` | **Create** — Phase 2 |
| `tests/ui/test_rpa_service.py` | **Create** — Phase 6 |
| `tests/ui/test_rpa_workflows.py` | **Create** — Phase 8 |
| `tests/unit/__init__.py` | **Create** — Phase 1 |
| `tests/unit/rpa/__init__.py` | **Create** — Phase 1 |
| `tests/unit/rpa/test_foundations.py` | **Create** — Phase 1 |
| `tests/unit/rpa/test_driver.py` | **Create** — Phase 2 |
| `tests/unit/rpa/test_targets.py` | **Create** — Phase 3 |
| `tests/unit/rpa/test_appstate.py` | **Create** — Phase 4 |
| `tests/unit/rpa/test_runner.py` | **Create** — Phase 5 |
| `tests/unit/rpa/test_vision.py` | **Create** — Phase 7 |
| `tests/unit/rpa/test_completeness.py` | **Create** — Phase 9 |
| `ruff.toml` | **Create** — Phase 1 |
| `Makefile` | **Create** — Phase 1 |
| `requirements-rpa.txt` | **Create** — Phase 1 |
| `requirements-dev.txt` | **Create** — Phase 1 |
| `docs/conf.py` | **Create** — Phase 1 (Sphinx) |
| `Resources/Rpa/Templates/manifest.json` | **Create** — Phase 7; **Edit** Phase 8 |
| `Resources/Rpa/Fixtures/world.json` | **Create** — Phase 2 (captured from real app) |
| `tools/caissa-rpa` | **Create** — Phase 6 |
| `pytest.ini` | **Edit** — Phase 1 (add markers; add `timeout` plugin config) |
| All existing `tests/test_*.py` | **Edit** — Phase 1 (add `pytestmark = pytest.mark.unit` only) |
| `docs/features/rpa-layer/production_readiness.md` | **Create** — Phase 9 |

---

## Phase 0 — Documentation & Process

*(Delivered on this PR — `docs/rpa-layer`. See feature_steps.md §Phase 0.)*

---

## Phase 1 — Foundations

### Session 1-A — Error hierarchy + Types

**Files to create/edit:**

- `bin/Code/Rpa/__init__.py` (create — 0 bytes)
- `bin/Code/Rpa/Errors.py` (create — write tests first, then implement)
- `bin/Code/Rpa/Types.py` (create — write tests first, then implement)
- `tests/unit/__init__.py` (create — 0 bytes)
- `tests/unit/rpa/__init__.py` (create — 0 bytes)
- `tests/unit/rpa/test_foundations.py` (create — write tests first, then implement)

**Scope:**

Create the `CaissaError` hierarchy and the three dependency-free types (`Rect`, `ElementRef`,
`Snapshot`) that every pure module imports, plus the test file containing `xfail` stubs for
all later phases.

**What to implement:**

1. `bin/Code/Rpa/Errors.py` — module docstring explaining this module hosts `CaissaError` per
   `docs/standards/error-handling.md` (first module to create it).
   - `CaissaError(Exception)` — base for all Caissa-specific errors
   - `RpaError(CaissaError)` — domain base
   - 15 specific exceptions (see §11 of feature_spec.md), each with one-line docstring

2. `bin/Code/Rpa/Types.py` — ZERO third-party imports (enforced by test).
   - `Rect(x: int, y: int, w: int, h: int)` frozen dataclass
   - `ElementRef(selector: "Selector", rect: Rect)` frozen dataclass (quoted forward ref)
   - `Snapshot(state_name: str, widget_tree: list[dict], timestamp_ms: float)` frozen dataclass

3. `tests/unit/rpa/test_foundations.py` — write tests first:
   - All `test_` functions in Phase 1 (see feature_steps.md §Phase 1)
   - All later-phase test names as `@pytest.mark.xfail(strict=True, reason="Requires Phase N …")`
     — this is the canonical `xfail` stub list that Phase 9 validates

**Tests this session makes green:**

- `test_caissa_error_is_exception_subclass`
- `test_rpa_error_is_caissa_error_subclass`
- `test_all_rpa_error_types_are_rpa_error_subclasses`
- `test_rect_is_frozen`
- `test_element_ref_is_frozen`
- `test_snapshot_is_frozen`
- `test_types_module_has_no_third_party_imports`
- `test_errors_module_has_no_third_party_imports`

**Spec refs:** NFR-1, NFR-6, §11

**Definition of done:**

- [ ] `bin/Code/Rpa/__init__.py` is 0 bytes
- [ ] All 17 exception classes present in `Errors.py` with RST docstrings
- [ ] `Types.py` has zero third-party imports (test green)
- [ ] All `xfail` stubs for Phases 2–9 in `test_foundations.py`
- [ ] All target tests green; no other tests broken
- [ ] `make lint` passes

**Suggested commit:** `chore(rpa): Phase 1-A — RPA error hierarchy and dependency-free types`

---

### Session 1-B — LogSetup + Makefile + ruff.toml + pytest markers

**Files to create/edit:**

- `bin/Code/Main/LogSetup.py` (create)
- `ruff.toml` (create)
- `Makefile` (create)
- `requirements-rpa.txt` (create)
- `requirements-dev.txt` (create)
- `docs/conf.py` (create)
- `pytest.ini` (edit — add markers + timeout plugin config)
- `tests/test_remote_control.py` (edit — add `pytestmark = pytest.mark.unit` line only)
- `tests/test_classical_invariant.py` (edit — add `pytestmark = pytest.mark.unit` line only)
- `tests/test_engine_game.py` (edit — add `pytestmark = pytest.mark.unit`)
- `tests/test_engine_responds.py` (edit — add `pytestmark = pytest.mark.unit`)
- `tests/test_sidebar_icon_consistency.py` (edit — add `pytestmark = pytest.mark.unit`)
- `tests/ui/test_overlay.py` (edit — add `pytestmark = pytest.mark.ui`)
- `tests/ui/test_classical.py` (edit — add `pytestmark = pytest.mark.ui`)

**Scope:**

Establish the tooling infrastructure: logging configuration, Makefile targets, ruff config,
dependency files, Sphinx config, and marker discipline for the existing test suite.

**What to implement:**

- `LogSetup.configure(level=None)` — reads `CAISSA_LOG_LEVEL`; sets root logger; call once
  from entry point; no-op if called again; module docstring explaining "entry point only"
- `ruff.toml` at repo root:
  ```toml
  include = ["bin/Code/Rpa/**", "bin/Code/Main/LogSetup.py", "tests/unit/rpa/**", "tools/caissa-rpa"]
  target-version = "py313"
  [lint]
  select = ["E", "W", "F", "I", "UP"]
  ```
- `Makefile`:
  - `PY` resolves via `$(shell git rev-parse --git-common-dir)/../.venv/bin/python3`
    with `PY?=python3` override
  - `make test` — `QT_QPA_PLATFORM=offscreen $(PY) -m pytest -m "unit or rpa" -v`
  - `make test-all` — `QT_QPA_PLATFORM=offscreen $(PY) -m pytest tests -v`
  - `make cov` — `--cov=Code.Rpa --cov-fail-under=90 --cov-branch --cov-config=.coveragerc`
  - `make test-ui` — `$(PY) -m pytest -m "ui or rpa_ui" -v`
  - `make test-cv` — `CAISSA_RPA_CV=1 $(PY) -m pytest -m rpa_cv -v`
  - `make lint` — `$(PY) -m ruff check --config ruff.toml`
  - `make docs` — `$(PY) -m sphinx docs/conf.py docs/rpa/api`
  - `make rpa-doctor` — `$(PY) -c "from Code.Rpa.Vision.Availability import probe; ..."`
  - `make help` — list all targets with descriptions

**Tests this session makes green:**

- `test_every_collected_test_has_exactly_one_suite_marker`
- `test_ruff_config_enforces_e722`
- `test_logsetup_configures_root_logger`
- `test_logsetup_reads_env_var`
- `test_rpa_timeout_below_pytest_timeout` *(also Phase 9 — first time green here)*

**Spec refs:** NFR-5, NFR-6, §14

**Definition of done:**

- [ ] `make lint` runs and reports `ruff.toml` rules (not the upstream `E722`-suppressing config)
- [ ] `make test` collects the existing 44 RC tests + classical invariant tests via marker
- [ ] `test_every_collected_test_has_exactly_one_suite_marker` green
- [ ] All existing tests still green
- [ ] Tracker updated: Phase 1 marked ✅

**Suggested commit:** `chore(rpa): Phase 1-B — tooling, markers, logging, Makefile`

---

## Phase 2 — Driver Seam + Contract Lock

### Session 2-A — rc_contract.json (BEFORE refactor)

**Files to create/edit:**

- `tests/ui/rc_contract.json` (create — captured against the pre-refactor binary)
- `tests/ui/test_rc_contract.py` (create)

**Scope:**

Capture the 25-verb wire contract before any refactor. This is the regression gate. The test
file must be green before Session 2-B begins.

**What to implement:**

- Run `tools/caissa-ctl` against the live app for each of the 25 verbs; capture response key
  sets and value types
- Write the JSON fixture
- 25 parametrised assertions in `test_rc_contract.py`:
  `test_verb_response_keys_match_golden[<verb>]` — response key set matches the fixture

**Tests this session makes green:**

- `test_verb_response_keys_match_golden[ping]` (and × 25)

**Spec refs:** §10

**Definition of done:**

- [ ] All 25 verbs captured in `rc_contract.json`
- [ ] All 25 parametrised assertions green against the pre-refactor binary
- [ ] `tests/test_remote_control.py` (44 tests) still green

**Suggested commit:** `test(rpa): Phase 2-A — record RemoteControl wire contract before refactor`

---

### Session 2-B — Driver seam

**Files to create/edit:**

- `bin/Code/Rpa/Driver.py` (create)
- `bin/Code/Rpa/Fakes.py` (create)
- `bin/Code/Debug/RemoteControl.py` (edit — extract to QtDriver; add lazy `_rpa()`)
- `tests/unit/rpa/test_driver.py` (create)

**Scope:**

Create the `Driver` plain base, `QtDriver`, `FakeDriver`, and `FakeClock`. Extract the 13
helper methods from RemoteControl into `QtDriver`. Zero behaviour change in any of the 25
original verbs — verified by `rc_contract.json` tests staying green.

**What to implement:**

- `Driver` plain base class — all 8 methods raise `NotImplementedError`
- `QtDriver(Driver)` — each method delegates to the extracted helper
- Helper methods in `QtDriver`: `_match_widget`, `_find_all_visible`, `_widget_info`,
  `_dump_ui`, `_click_widget`, `_click_toolbar`, `_click_tab`, `_set_field`,
  `_combo_select`, `_get_topmost_dialog`, `_dialog_info`, `_dialog_button`, `_screenshot`
- `_force_cancel` moved verbatim with all its comments preserved
- `RemoteControl`: existing verb handlers delegate to `QtDriver` methods; `_dlog` → `logger.debug`;
  `faulthandler` gated on `CAISSA_RPA_FAULTHANDLER=1`; lazy `_rpa()` accessor
- `FakeDriver(Driver)` — `World`-based implementation; `FakeClock`
- `Resources/Rpa/Fixtures/world.json` — run `tools/caissa-rpa capture-world` (or stub for now)

**Tests this session makes green:**

- `test_driver_base_raises_not_implemented_for_all_methods`
- `test_fake_driver_overrides_all_driver_methods`
- `test_qt_driver_overrides_all_driver_methods`
- `test_fake_clock_advance_updates_now`
- `test_fake_clock_run_due_fires_scheduled_callbacks`
- `test_fake_driver_snapshot_returns_world_state`
- `test_fake_driver_defer_schedules_via_fake_clock`
- `test_rpa_disabled_by_env_serves_no_rpa_verbs`
- `test_importing_runner_does_not_import_cv2`
- `test_no_pyside6_import_outside_allowlist`
- All 25 `test_verb_response_keys_match_golden[*]` still green (regression gate)
- All 44 `tests/test_remote_control.py` still green

**Spec refs:** NFR-2, NFR-9, §5

**Definition of done:**

- [ ] All 25 original verbs still pass `rc_contract.json` assertions
- [ ] All 44 `test_remote_control.py` tests still green
- [ ] `_force_cancel` diff reads as a pure method move — no logic changes
- [ ] RST docstrings for all new classes and methods
- [ ] Tracker updated: Phase 2 marked ✅

**Suggested commit:** `refactor(rpa): Phase 2 — extract RemoteControl helpers into QtDriver seam`

---

## Phases 3–9

*(Detailed session breakdowns will be written when the phase is the current one — generated from
the Piece Plan prompt with the spec and steps doc as context. The test names and spec refs are
already in `feature_steps.md`.)*

---

## Final Verification

```bash
make test        # all green
make test-all    # cross-check: markers and filesystem agree
make cov         # ≥ 90 % Code.Rpa, branch=true
make lint        # zero issues
make docs        # zero warnings
make test-ui     # integration suite green
```

Update `feature_steps.md`: mark all phases ✅.
Move `docs/features/rpa-layer/` to `docs/features/_archive/rpa-layer/`.

---

## Session Summary Table

| Session | Phase | What it delivers | New tests |
|---------|-------|-----------------|-----------|
| 1-A | Foundations | Error hierarchy, Types | ~8 + xfail stubs |
| 1-B | Foundations | LogSetup, Makefile, ruff, markers | ~5 |
| 2-A | Driver seam | rc_contract.json captured | 25 |
| 2-B | Driver seam | Driver/QtDriver/Fakes extracted | ~12 |
| 3-A | Targets | Selector, Target, compact parser | ~10 |
| 4-A | State model | AppState, StateGraph, Dijkstra | ~8 |
| 5-A | Runner | Journal, Activities, Runner core | ~28 |
| 6-A | Service | Service, 10 verbs, client, CLI | ~10 |
| 7-A | Vision | All 5 Vision modules | ~11 |
| 8-A | Workflows | Registry + 4 workflows | ~6 |
| 9-A | Production | Completeness, readiness, docs | ~7 |

**Total: ~11 sessions, ~130 tests.**
