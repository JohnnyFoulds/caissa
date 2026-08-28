# RPA Layer — Implementation Steps

Living implementation tracker for the Caissa RPA Layer feature.
Updated after each phase is completed.

**Spec reference:** [feature_spec.md](feature_spec.md)

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ⬜ | Not started |
| 🔄 | In progress |
| ✅ | Complete |

---

## Phase 0 — Documentation & Process ✅

**Branch:** `docs/rpa-layer`

**Files:**

- `docs/templates/` (create — 6 Caissa-adapted template files)
- `docs/claude_code/prompts.md` (create — 11-prompt library, filled in for RPA)
- `docs/process/sdd-workflow.md` (create — THE ROUTINE + 8 gates)
- `docs/features/rpa-layer/initial_idea.md` (create — FROZEN)
- `docs/features/rpa-layer/feature_spec.md` (create — this feature's full R/I/P/Q/N)
- `docs/features/rpa-layer/feature_steps.md` (create — this file)
- `docs/features/rpa-layer/implementation_plan.md` (create — session breakdown)
- `docs/rpa/README.md`, `concepts.md`, `uipath-mapping.md`, `states.md`,
  `glossary.md`, `decisions.md`, `state-machine.md` (create — design-time docs)
- `docs/standards/spec-driven-development.md` (edit — §5 feature-directory convention)
- `docs/standards/coding-standards.md` (edit — §3.2 Protocol clarification; §5 ruff note)
- `docs/standards/error-handling.md` (edit — record `Errors.py` location)
- `docs/ui-testing.md` (edit — §7.1 CV amendment; fix stale `tests/unit/` refs)
- `CLAUDE.md` (edit — add rpa scope; `docs/features/` + `docs/process/` paths)
- `CHANGELOG.md` (edit — `[Unreleased] Added`)
- `.gitignore` (edit — add `docs/_tmp/` and `docs/rpa/api/`)

**What we deliver:**

- Problem statement and frozen business requirements (`initial_idea.md`)
- Full R/I/P/Q/N spec (Gate A complete before Phase 1 begins)
- All planned test names recorded in this document
- Product doc design-time subset (state machine, concepts, ontology, states, glossary, decisions)
- Process document (`sdd-workflow.md`) and 8-gate checklist
- All standards amendments

**Test names (all `xfail(strict=True)` until owning phase lands):**

All test names in the table below are recorded in `implementation_plan.md` by their owning
session. `xfail` stubs live in `tests/unit/rpa/` — created in Phase 1 as the first file.
Phase 9 asserts every name in this list exists in the suite.

**Spec refs:** BR-1..4, §13, §14

---

## Phase 1 — Foundations ✅

**Branch:** `chore/rpa-foundations`
**Docs shipped (Gate H):** `docs/rpa/api/` scaffold builds green (Sphinx config, `make docs`)

**Files:**

- `bin/Code/Rpa/__init__.py` (create — 0 bytes)
- `bin/Code/Rpa/Errors.py` (create)
- `bin/Code/Rpa/Types.py` (create)
- `bin/Code/Main/LogSetup.py` (create)
- `ruff.toml` (create — root, scoped to Caissa paths via `include`)
- `Makefile` (create — `test`, `test-all`, `cov`, `test-ui`, `test-cv`, `lint`, `docs`, `rpa-doctor`)
- `requirements-rpa.txt` (create — `opencv-python-headless`, `pytesseract`)
- `requirements-dev.txt` (create — `sphinx`, `pytest-timeout`, `pytest-cov`)
- `pytest.ini` (edit — apply `pytestmark = pytest.mark.unit` to all existing test modules;
  add `rpa`, `rpa_ui`, `rpa_cv` markers; add `timeout` plugin config)
- `tests/unit/__init__.py` (create — 0 bytes, mirrors `tests/ui/__init__.py`)
- `tests/unit/rpa/__init__.py` (create — 0 bytes)
- `tests/unit/rpa/test_foundations.py` (create — Phase 1 tests + `xfail` stubs for all later phases)
- `docs/conf.py` (create — Sphinx autodoc config)
- `tests/test_remote_control.py` (edit — add `pytestmark = pytest.mark.unit` header ONLY)
- `tests/test_classical_invariant.py` (edit — add `pytestmark = pytest.mark.unit` header ONLY)
- ... (all existing test files — same edit: add pytestmark)

**What we implement:**

- `CaissaError(Exception)` in `Errors.py` with RST docstring
- `RpaError(CaissaError)` — domain base
- 15 specific exceptions (see §11 of feature_spec.md), each with one-line docstring
- `Rect(x, y, w, h)` frozen dataclass in `Types.py`
- `ElementRef(selector, rect)` frozen dataclass in `Types.py`
- `Snapshot(state_name, widget_tree, timestamp_ms)` frozen dataclass in `Types.py`
- `LogSetup.configure(level=None)` — call once from entry point; reads `CAISSA_LOG_LEVEL`
- `Makefile` targets: `test`, `test-all`, `cov`, `test-ui`, `test-cv`, `lint`, `docs`, `rpa-doctor`, `help`
  - `make lint` passes `--config ruff.toml` explicitly (D11)
  - Venv resolved via `git rev-parse --git-common-dir` with `PY=` override
- `ruff.toml` at repo root — `include` scoped to Caissa paths; `select = ["E","W","F","I","UP"]`;
  `target-version = "py313"`; `E722` not suppressed

**TDD test cases (`tests/unit/rpa/test_foundations.py`):**

- `test_caissa_error_is_exception_subclass`
- `test_rpa_error_is_caissa_error_subclass`
- `test_all_rpa_error_types_are_rpa_error_subclasses`
- `test_rect_is_frozen`
- `test_element_ref_is_frozen`
- `test_snapshot_is_frozen`
- `test_types_module_has_no_third_party_imports` — AST-parse `Types.py`; assert no numpy/cv2 (N-RPA-1)
- `test_errors_module_has_no_third_party_imports`
- `test_every_collected_test_has_exactly_one_suite_marker` — `pytest_collection_modifyitems` hook
- `test_ruff_config_enforces_e722` — run ruff on a fixture with bare `except:`; assert E722 reported
- `test_logsetup_configures_root_logger`
- `test_logsetup_reads_env_var`
- xfail stubs for every test name in Phases 2–9 (see `implementation_plan.md`)

**Spec refs:** NFR-1, NFR-5, NFR-6, §11

---

## Phase 2 — Driver Seam + Contract Lock ✅

**Branch:** `refactor/rpa-driver-seam`
**Docs shipped (Gate H):** `docs/rpa/extending.md` (driver contract section)

**Files:**

- `tests/ui/rc_contract.json` (create — 25-verb response-shape snapshot, BEFORE any refactor)
- `bin/Code/Rpa/Driver.py` (create)
- `bin/Code/Rpa/Fakes.py` (create)
- `bin/Code/Debug/RemoteControl.py` (edit — extract helpers into QtDriver; add lazy `_rpa()`)
- `tests/unit/rpa/test_driver.py` (create)
- `tests/ui/test_rc_contract.py` (create — 25 parametrised assertions)

**What we implement:**

- `Driver` plain base class with all methods raising `NotImplementedError`
  (`snapshot`, `click`, `set_text`, `select_combo`, `trigger_action`, `now`, `defer`, `capture`)
- `QtDriver(Driver)` — delegating to the extracted RemoteControl helpers
- `FakeDriver(Driver)` + `FakeClock` in `Fakes.py`
- `World` dataclass — the fixture describing a fake app state
- `Resources/Rpa/Fixtures/world.json` — generated from real app (see `tools/caissa-rpa capture-world`)
- RemoteControl: all 13 helper methods extracted into `QtDriver`; JSON response shaping stays in RC;
  `_dlog` calls replaced by `logger.debug`; `faulthandler` gated on `CAISSA_RPA_FAULTHANDLER=1`;
  lazy `_rpa()` accessor; `CAISSA_RPA=0` kill switch
- `_force_cancel()` moved verbatim — comments preserved

**Zero behaviour change in RemoteControl for any of the 25 original verbs.**

**TDD test cases:**

- `test_driver_base_raises_not_implemented_for_all_methods`
- `test_fake_driver_overrides_all_driver_methods`
- `test_qt_driver_overrides_all_driver_methods`
- `test_fake_clock_advance_updates_now`
- `test_fake_clock_run_due_fires_scheduled_callbacks`
- `test_fake_driver_snapshot_returns_world_state`
- `test_fake_driver_defer_schedules_via_fake_clock`
- `test_actuating_on_deleted_widget_raises_target_not_found` — `QtDriver` with `shiboken6`
- `test_verb_response_keys_match_golden[ping]` (parametrised × 25)
- `test_rpa_disabled_by_env_serves_no_rpa_verbs`
- `test_importing_runner_does_not_import_cv2`
- `test_no_pyside6_import_outside_allowlist` — AST-parse all `.py` in `bin/Code/Rpa/`

**Spec refs:** FR-1, NFR-2, NFR-9, §5, §10

---

## Phase 3 — Targets + Object Resolver ✅

**Branch:** `feat/rpa-targets`
**Docs shipped (Gate H):** `docs/rpa/selectors.md`

**Files:**

- `bin/Code/Rpa/Targets.py` (create)
- `bin/Code/Rpa/Resolve.py` (create — object tier only; CV stubs)
- `tests/unit/rpa/test_targets.py` (create)

**What we implement:**

- `Selector(tier, cls, object_name, text, text_exact, role, scope, index, image, threshold)` dataclass
- `Target(selector, anchor, direction, max_distance, timeout_ms)` dataclass
- Compact-string parser and JSON codec
- `TargetResolver.visible_elements(snapshot) → list[ElementRef]` — cached per pump
- `TargetResolver.resolve_one(target, snapshot) → ElementRef` — raises `AmbiguousMatchError` on ties
- Object tier confidence: exact `object_name` = 1.00, exact text = 0.95, substring = 0.80, class-only = 0.60
- Anchor resolution: filter by `Rect` direction predicate and distance
- `Selector` construction raises if no discriminating field is set

**TDD test cases:**

- `test_selector_compact_string_roundtrip`
- `test_selector_json_roundtrip`
- `test_selector_requires_discriminating_field`
- `test_resolve_object_exact_name`
- `test_resolve_object_exact_text`
- `test_resolve_ambiguous_raises`
- `test_resolve_anchor_right_of`
- `test_object_confidence_exact_name_is_one`
- `test_object_confidence_class_only_is_0_60`
- `test_fallback_tier_win_emits_warning`

**Spec refs:** FR-4, §6

---

## Phase 4 — State Model ✅

**Branch:** `feat/rpa-state-model`
**Docs shipped (Gate H):** `docs/rpa/states.md` finalised against code

**Files:**

- `bin/Code/Rpa/AppState.py` (create)
- `tests/unit/rpa/test_appstate.py` (create)

**What we implement:**

- State constants (`DIALOG_CONFIG`, `DIALOG_OTHER`, `GAME_OVER`, `ENGINE_THINKING`,
  `PLAYING`, `MANAGER_OTHER`, `HOME`, `UNKNOWN`)
- `recognise(snapshot: Snapshot) → str` — dialog-first priority
- `Transition(source, target, name, cost, min_settle_ms, action, verify)` dataclass
- `StateGraph` — transition registry + Dijkstra `plan(from_state, to_state) → list[Transition]`
- All 8 states reachable from every other state (test asserts this)

**TDD test cases:**

- `test_recognise_dialog_config_priority`
- `test_recognise_home`
- `test_recognise_unknown_fallback`
- `test_plan_home_to_playing` — returns a non-empty path
- `test_plan_avoids_force_cancel_when_cheaper_path_exists`
- `test_every_state_can_reach_home`
- `test_every_force_cancel_edge_declares_min_settle_at_least_600`
- `test_plan_rejects_unreachable_state`

**Spec refs:** FR-5, §7

---

## Phase 5 — Runner + Journal + Activities ✅

**Branch:** `feat/rpa-runner`
**Docs shipped (Gate H):** `docs/rpa/activities.md`; `docs/rpa/state-machine.md` worked traces verified

**Files:**

- `bin/Code/Rpa/Journal.py` (create)
- `bin/Code/Rpa/Activities.py` (create)
- `bin/Code/Rpa/Runner.py` (create)
- `tests/unit/rpa/test_runner.py` (create — ~45 tests)

**What we implement:**

- `StepRecord`, `RunRecord` dataclasses with JSON serialisation
- `SubState` enum — exactly 14 members (the `state-machine.md` canonical list)
- `Context` — shared state across a run's pumps
- Frame stack (`SequenceFrame`, `RetryScopeFrame`)
- `Runner.pump() → bool` — the single pump; `False` when terminal
- `Activity` plain base class with `precondition`, `execute`, `postcondition`, `compensate`,
  `prepare_next` methods raising `NotImplementedError`
- All UiPath-named concrete activities (see §5 of spec):
  `Click`, `TypeInto`, `SelectItem`, `GetText`, `ElementExists`, `TakeScreenshot`,
  `OpenConfig`, `CloseDialog`, `SwitchTab`, `Sequence`, `RetryScope`
- `Journal.persist(run_record, run_dir)` and `Journal.load(run_dir) → RunRecord`
- `UserData/RpaRuns/<run_id>/` layout

**TDD test cases (`tests/unit/rpa/test_runner.py`):**

- `test_sub_state_enum_has_exactly_14_members`
- `test_state_machine_doc_lists_every_substate` — diff enum against `state-machine.md` literal list
- `test_happy_path_completes_to_succeeded`
- `test_precondition_false_triggers_convergence`
- `test_convergence_exhausts_budget_transitions_to_unwind`
- `test_postcondition_retried_within_deadline`
- `test_postcondition_timeout_triggers_decide_recovery`
- `test_decide_recovery_retryable_backs_off`
- `test_decide_recovery_compensable_compensates`
- `test_compensate_success_retries_step`
- `test_compensate_fail_unwinds`
- `test_unwind_calls_compensate_in_reverse`
- `test_frame_pop_resumes_parent`
- `test_retry_scope_re_enters_on_failure`
- `test_no_sleep_call_anywhere` — monkeypatch `time.sleep` to raise; run full workflow
- `test_one_pump_one_transition_max` — count driver actuations across 100 pumps; assert ≤ 1 per pump
- `test_run_timeout_triggers_cancelling`
- `test_run_timeout_ms_less_than_pytest_timeout`
- `test_second_concurrent_run_is_rejected`
- `test_rpa_cancel_sets_cancelling_state`
- `test_settled_ms_not_pumps` — settle expressed in ms; advancing clock by settle_ms unblocks it
- `test_journal_written_on_terminal_transition`
- `test_journal_env_block_records_dpr_theme_and_cv_availability`
- `test_run_id_scheme_is_timestamp_plus_hex`
- `test_backoff_reproducible_from_run_id`
- `test_pump_reentrancy_guard_prevents_nested_pump`
- `test_cancelling_transitions_to_cancelled_via_unwind`
- xfail: `test_every_rpa_verb_returns_under_200ms_while_run_active` *(requires Phase 6)*
- xfail: `test_run_progresses_while_a_modal_dialog_is_open` *(requires Phase 6)*

**Spec refs:** FR-2, FR-6, NFR-3, NFR-10, §8

---

## Phase 6 — Service + `rpa_*` Verbs + Client/CLI ✅

**Branch:** `feat/rpa-service`
**Docs shipped (Gate H):** `docs/rpa/wire-protocol.md`, `docs/rpa/cli.md`, `docs/rpa/quickstart.md`
  — quickstart executed verbatim as acceptance test

**Files:**

- `bin/Code/Rpa/Service.py` (create)
- `tests/ui/rpa_client.py` (create)
- `tools/caissa-rpa` (create)
- `bin/Code/Debug/RemoteControl.py` (edit — add 10 `rpa_*` verb handlers delegating to Service)
- `tests/ui/test_rpa_service.py` (create — `rpa_ui` suite)

**What we implement:**

- `RpaService` — run registry, own 50 ms QTimer, `rpa_*` verb handlers
- All 10 verbs (§10 of spec)
- `CaissaRpaClient(run_and_wait, poll_interval=250)` — wraps `CaissaClient`
- `tools/caissa-rpa` CLI: `run`, `status`, `journal`, `find`, `doctor`

**TDD test cases:**

- `test_every_rpa_verb_returns_under_200ms_while_run_active` *(was xfail — now green)*
- `test_run_progresses_while_a_modal_dialog_is_open` *(was xfail — now green)*
- `test_rpa_run_returns_run_id`
- `test_rpa_status_returns_pending_before_pump`
- `test_rpa_cancel_accepted_during_run`
- `test_rpa_find_returns_element_list`
- `test_rpa_state_returns_current_state`
- `test_rpa_capabilities_returns_cv_flags`
- `test_rpa_disabled_env_blocks_all_rpa_verbs_but_not_originals`
- Quickstart smoke: `test_quickstart_executed_verbatim`

**Spec refs:** FR-3, FR-8, FR-9, NFR-4, §10

---

## Phase 7 — Vision ✅

**Branch:** `feat/rpa-vision`
**Docs shipped (Gate H):** `docs/rpa/vision.md`

**Files:**

- `bin/Code/Rpa/Vision/__init__.py` (create — 0 bytes)
- `bin/Code/Rpa/Vision/Availability.py` (create)
- `bin/Code/Rpa/Vision/Capture.py` (create)
- `bin/Code/Rpa/Vision/Template.py` (create)
- `bin/Code/Rpa/Vision/Ocr.py` (create)
- `bin/Code/Rpa/Vision/Manifest.py` (create)
- `bin/Code/Rpa/Resolve.py` (edit — wire in image + OCR tiers)
- `Resources/Rpa/Templates/manifest.json` (create — empty manifest)
- `tests/unit/rpa/test_vision.py` (create — `rpa_cv` marked)

**What we implement:**

- `Vision.Availability.probe() → AvailabilityFlags` — cached; never raises
- `Vision.Capture.grab(widget) → Screenshot` — handles `bytesPerLine()` padding; RGB rule
- `Screenshot.logical() → ndarray` — `INTER_AREA` resize by 1/dpr
- `Vision.Template.find_all(screenshot, template) → list[Match]` — NMS at IoU 0.3
- Multi-scale fallback at `[0.95, 1.05, 0.90, 1.10]` with `logger.warning` on non-1.0 win
- `Vision.Ocr.find_phrase(screenshot, phrase) → list[Match]` — grouped by `(block, par, line)`
- `Vision.Manifest.load_and_verify(path) → Manifest` — sha256 check
- Image and OCR tiers wired into `TargetResolver`

**TDD test cases (all `rpa_cv` marked — skipped by default and when offscreen):**

- `test_capture_rgb_channel_order`
- `test_capture_handles_byteperline_padding` — odd-width QImage
- `test_screenshot_logical_resizes_by_dpr`
- `test_template_match_finds_known_template`
- `test_template_multi_scale_warns_on_nonunit_scale`
- `test_ocr_finds_multiword_phrase`
- `test_ocr_grouped_by_block_par_line`
- `test_manifest_hashes_match_files`
- `test_manifest_missing_entry_raises`
- `test_availability_no_cv_returns_reason_with_install_command`
- `test_no_toplevel_numpy_or_cv2_import_outside_vision`

**Spec refs:** FR-7, NFR-7, NFR-9, §9

---

## Phase 8 — Workflows + Regression Suite ✅

**Branch:** `feat/rpa-workflows`
**Docs shipped (Gate H):** `docs/rpa/authoring-workflows.md`, `docs/rpa/testing.md`

**Files:**

- `bin/Code/Rpa/Workflows/__init__.py` (create — 0 bytes)
- `bin/Code/Rpa/Workflows/Registry.py` (create)
- `bin/Code/Rpa/Workflows/smoke_home.py` (create)
- `bin/Code/Rpa/Workflows/classical_invariant.py` (create)
- `bin/Code/Rpa/Workflows/play_a_game.py` (create)
- `bin/Code/Rpa/Workflows/config_roundtrip.py` (create)
- `Resources/Rpa/Templates/manifest.json` (edit — add templates for each workflow)
- `tests/ui/test_rpa_workflows.py` (create — `rpa_ui` suite)

**What we implement:**

- `Registry.register(name, workflow_fn)` and `Registry.get(name)`
- `smoke_home` — converge to HOME; assert state is HOME
- `classical_invariant` — open Config dialog; assert all original labels present; close
- `play_a_game` — start a game against engine; play 3 moves; verify moves played
- `config_roundtrip` — open Config; change player name; close; reopen; assert name saved

**TDD test cases:**

- `test_registry_register_and_get`
- `test_registry_unknown_raises_workflow_not_found_error`
- `test_smoke_home_succeeds`
- `test_classical_invariant_workflow_passes_on_classical_mode`
- `test_config_roundtrip_succeeds`
- `test_every_workflow_template_ref_is_in_manifest`

**Spec refs:** FR-10, §13

---

## Phase 9 — Production Readiness ⬜

**Branch:** `chore/rpa-production-readiness`
**Docs shipped (Gate H):** `docs/rpa/user-guide.md`, `docs/rpa/troubleshooting.md`,
  `docs/rpa/operations.md`, `docs/rpa/extending.md` completed; Gate E checklist

**Files:**

- `docs/rpa/user-guide.md` (create)
- `docs/rpa/troubleshooting.md` (create)
- `docs/rpa/operations.md` (create)
- `docs/features/rpa-layer/production_readiness.md` (create — Gate E checklist + findings)
- `tests/unit/rpa/test_completeness.py` (create)

**What we implement:**

- Production readiness review (Gate E) and all findings tracked to resolution
- CI proposal documented (D7 resolved one way or the other)
- `quickstart.md` executed verbatim as acceptance test (second time)

**TDD test cases:**

- `test_every_planned_test_name_exists_in_suite` — reads `feature_steps.md`, diffs against collected tests
- `test_every_public_callable_in_rpa_has_docstring`
- `test_make_docs_builds_with_zero_warnings`
- `test_no_pyside6_import_outside_allowlist` — (was already in Phase 2; re-run clean)
- `test_rpa_timeout_below_pytest_timeout`
- `test_cv2_absent_from_sys_modules_after_plain_start`
- `test_quickstart_executed_verbatim` (second execution — regression guard)

**Spec refs:** NFR-5, NFR-6, §14

---

## Verification

After each phase completes, mark it ✅ in the phase heading above.

After all phases are complete:

```bash
make test        # all green
make test-all    # cross-check markers match filesystem
make cov         # ≥ 90 % Code.Rpa, branch=true
make lint        # zero issues
make docs        # zero warnings
make test-ui     # integration suite green
```
