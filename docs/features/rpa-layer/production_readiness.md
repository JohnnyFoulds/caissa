# RPA Layer — Production Readiness (Gate E)

**Feature:** Caissa RPA Layer  
**Phase:** 9 — Production Readiness  
**Date:** 2026-08-28  
**Status:** PASSED — all findings resolved

---

## Gate E Checklist

### 1. Correctness

- [x] Unit test suite: 156 passed, 0 failures (`make test`)
- [x] All xfail stubs for Phases 7–9 resolved or remain as intended xfail placeholders
- [x] `tests/test_classical_invariant.py` green throughout all 9 phases
- [x] `tests/test_remote_control.py` (44 tests) green throughout — Phase 2 compatibility gate
- [x] Runner state machine: all 14 sub-states enumerated and doc-asserted
- [x] Three deadlines: RUN_TIMEOUT_MS=90 000 < pytest timeout (120 000) − 10 000 ms headroom
- [x] `_step_compensated` flag prevents infinite COMPENSATE→retry loops
- [x] DECIDE_RECOVERY backoff guard: `step_attempts > 0` required

### 2. Classical Invariant impact

- [x] No widget, toolbar entry, menu entry, mode JSON, QSS rule, overlay, or config key added
- [x] `CAISSA_RPA=0` kill switch verified: all 25 original verbs work; `Code.Rpa` never enters `sys.modules`
- [x] `RemoteControl.py` changes are pure delegation refactors; content unchanged for the 44-test gate
- [x] `classical_invariant` workflow is a runnable regression check

### 3. Non-functional

- [x] NFR-4 (200 ms response): all `rpa_*` verbs return in < 200 ms; `test_every_rpa_verb_returns_under_200ms_while_run_active` (rpa_ui)
- [x] NFR-5: no `time.sleep()` in the runner (monkeypatched to raise in tests)
- [x] NFR-6: cv2 absent from `sys.modules` after plain app start
- [x] NFR-7: no full-window pixel diffs; templates verified by sha256 manifest
- [x] NFR-8: capture via `widget.grab()` — no OS screen-recording permission required
- [x] NFR-9: Vision tiers optional; object-tier RPA works without cv2/tesseract

### 4. Architecture invariants

- [x] N-RPA-1: `Types.py` is dependency-free (enforced by `test_no_toplevel_numpy_or_cv2_import_outside_vision`)
- [x] N-RPA-2: only `Driver.py`, `Vision/Capture.py`, `Service.py` import PySide6 (enforced by `test_no_pyside6_import_outside_allowlist`)
- [x] `ElementRef` holds selector string, not Qt pointer; re-resolved + `isValid`-checked at actuation
- [x] One pump = at most one sub-state transition and at most one driver actuation
- [x] No bare `import PySide6` outside allowlist (confirmed by completeness test)

### 5. Documentation

- [x] `docs/rpa/README.md` — index (Phase 0)
- [x] `docs/rpa/concepts.md` — mental model (Phase 0)
- [x] `docs/rpa/state-machine.md` — formal spec (Phase 0, updated Phase 5)
- [x] `docs/rpa/activities.md` — activity catalogue (Phase 5)
- [x] `docs/rpa/wire-protocol.md` — 10 verb schemas (Phase 6)
- [x] `docs/rpa/cli.md` — CLI reference (Phase 6)
- [x] `docs/rpa/quickstart.md` — end-to-end tutorial (Phase 6)
- [x] `docs/rpa/vision.md` — CV/OCR guide (Phase 7)
- [x] `docs/rpa/authoring-workflows.md` — workflow authoring (Phase 8)
- [x] `docs/rpa/testing.md` — test harness guide (Phase 8)
- [x] `docs/rpa/user-guide.md` — user guide (Phase 9)
- [x] `docs/rpa/troubleshooting.md` — symptom→cause→fix (Phase 9)
- [x] `docs/rpa/operations.md` — journals, retention, diagnostics (Phase 9)
- [x] All public callables in `Code.Rpa` have RST docstrings (enforced by `test_every_public_callable_in_rpa_has_docstring`)

### 6. Test completeness

- [x] `test_every_planned_test_name_exists_in_suite` — all test names from `feature_steps.md` found
- [x] Every test has exactly one suite marker (`test_every_collected_test_has_exactly_one_suite_marker`)
- [x] `rpa_cv` tests skip under `QT_QPA_PLATFORM=offscreen` and when cv2 absent

### 7. Error handling

- [x] All new Caissa modules raise `CaissaError` subclasses
- [x] Every `logger.error()` includes `exc_info=True`
- [x] Every `raise ... from exc` wraps lower-level exceptions
- [x] `VisionUnavailableError` message is the install command
- [x] `RunAlreadyActiveError` message includes the active run_id and sub-state
- [x] `ManifestError` message includes the fix instructions

### 8. CI proposal (D7)

**Decision:** CI is proposed but NOT added in this PR.

Rationale: Adding a GitHub Actions workflow that runs on push to `JohnnyFoulds/caissa`
is an outward-facing change that requires Johannes's explicit approval.

**Recommended next step:** Create a `.github/workflows/rpa-unit.yml` that runs
`make test` on every push to `main` and every PR.  The `rpa_ui` and `rpa_cv` suites
are excluded from CI (they require a display + running Caissa process).

---

## Findings

### F1 — `_WORKFLOW_REGISTRY` coupling (RESOLVED — Phase 8)

`test_service.py` imported `_WORKFLOW_REGISTRY` directly from `Service.py`.
After Phase 8 moved the registry to `Workflows.Registry`, the import was updated to
`from Code.Rpa.Workflows.Registry import _REGISTRY as _WORKFLOW_REGISTRY`.

### F2 — N-RPA-2 violation in Resolve.py (RESOLVED — Phase 9)

`_image_candidates()` in `Resolve.py` imported `PySide6.QtGui.QImage` inside the
function to load template PNGs.  Fixed by adding `load_template(path)` to
`Vision/Template.py` (cv2-only) and calling it from `Resolve.py`.

### F3 — Missing `__init__` docstrings (RESOLVED — Phase 9)

Six public callables were missing docstrings:
- `Fakes.FakeClock.__init__`, `Fakes.FakeDriver.__init__`
- `Resolve._Candidate.__init__`
- `Service._ConvergeActivity.precondition/execute/postcondition`

All docstrings added.

---

## Archive

On completion of Phase 9, the `docs/features/rpa-layer/` directory should be
archived to `docs/features/_archive/rpa-layer/` with `git mv` so history follows.
The `**Status:**` front matter on each artefact becomes `Completed 2026-08-28`.
