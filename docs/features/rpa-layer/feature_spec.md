# RPA Layer — Software Design Document

**Status:** Specified — implementation pending  
**Branch:** phases `feat/rpa-*` (one per phase; see feature_steps.md)  
**Initial idea:** [initial_idea.md](initial_idea.md)  
**Phase tracker:** [feature_steps.md](feature_steps.md)

---

## 1. Problem Statement

Caissa's `RemoteControl.py` is a 25-verb Unix-socket command server — effectively a hand-rolled
RPA driver — but it has no engine: no state model, no pre/postcondition contract, no retry, no
compensation, no workflow composition. Every automation is an unguarded fire-and-forget socket
command that can leave the app in an undefined state if the UI was not where the caller assumed.

This feature builds a formal closed-loop RPA engine above RemoteControl, encoding the 5-step
guard pattern as first-class machinery (state-driven, contract-verified, compensating), with
UiPath's vocabulary for the user-facing API. It serves two purposes equally: automated
regression testing (especially the Classical Invariant) and reliable interactive dev/debug
driving of the app.

---

## 2. Requirements

### 2.1 Business Requirements

| ID | Requirement |
| --- | --- |
| BR-1 | Provide a closed-loop automation engine above RemoteControl that encodes the 5-step guard pattern. |
| BR-2 | Enable automated regression testing of Caissa UI, especially the Classical Invariant. |
| BR-3 | Enable reliable interactive app driving for dev/debug. |
| BR-4 | Use UiPath ontology for the user-facing Activity API. |

### 2.2 Functional Requirements

| ID | Requirement |
| --- | --- |
| FR-1 | The system **MUST** provide a `Runner` that executes workflows as a step-pumped state machine on its own QTimer without blocking the Qt main thread. |
| FR-2 | The system **MUST** enforce the 5-step closed loop: CHECK_PRE → (CONVERGE →) ACT → SETTLE → VERIFY → STEP_EXIT / recovery. |
| FR-3 | The system **MUST** provide 10 `rpa_*` verbs via RemoteControl that follow the job+status polling model. No blocking server-side verb. |
| FR-4 | The system **MUST** provide a `Selector` / `Target` model with tiered resolution: object → image → OCR. |
| FR-5 | The system **MUST** provide an `AppState` model with 8 states, Dijkstra planner, and convergence. |
| FR-6 | The system **MUST** record a `RunRecord` / `StepRecord` journal to `UserData/RpaRuns/<run_id>/journal.json`. |
| FR-7 | The system **MUST** provide CV/OCR-based location as a fallback tier, with DPR normalisation and multi-scale fallback. |
| FR-8 | The system **MUST** support `dry_run` mode via `FakeDriver` without needing a live Qt app. |
| FR-9 | The system **SHOULD** provide a CLI (`tools/caissa-rpa`) and a polling client (`CaissaRpaClient`). |
| FR-10 | The system **MUST** provide at least 4 built-in workflows: `smoke_home`, `classical_invariant`, `play_a_game`, `config_roundtrip`. |

### 2.3 Non-Functional Requirements

| ID | Requirement |
| --- | --- |
| NFR-1 | N-RPA-1: `Types.py` **MUST** have zero third-party imports. All pure modules import it. |
| NFR-2 | N-RPA-2: Only `Driver.py`, `Vision/Capture.py`, and `Service.py` **MAY** import PySide6. |
| NFR-3 | N-RPA-3: No `time.sleep()` anywhere in the package — enforced by a test. |
| NFR-4 | N-RPA-4: `rpa_*` verbs **MUST** return in < 200 ms while a run is active. |
| NFR-5 | N-RPA-5: Unit test coverage for `Code.Rpa` **MUST** be ≥ 90 % (branch), omitting the Qt-touching and test-double modules. |
| NFR-6 | N-RPA-6: All public and non-public callables **MUST** have RST/Sphinx docstrings. |
| NFR-7 | N-RPA-7: CV assertions **MUST NOT** use full-window pixel equality — template-presence and OCR-location only. |
| NFR-8 | N-RPA-8: No special OS permissions required — capture via `widget.grab()` / `QTest`, never `pyautogui`, `mss`, or CoreGraphics. |
| NFR-9 | N-RPA-9: `cv2` and `numpy` **MUST NOT** appear in `sys.modules` after a plain app start without an `rpa_*` verb. |
| NFR-10 | N-RPA-10: The run deadline **MUST** be 90 000 ms — at least 30 s below `pytest.ini` timeout. |

### 2.4 Constraints & Assumptions

- Placement: `bin/Code/Rpa/`; RemoteControl modified to serve it.
- Python 3.13 features acceptable; runtime declared floor `>=3.12`.
- No ABCs or `typing.Protocol` — plain base classes raising `NotImplementedError`.
- `CaissaError` lives in `bin/Code/Rpa/Errors.py` — this feature creates it.
- Optional dependencies: `requirements-rpa.txt` (cv2-headless, pytesseract) and
  `requirements-dev.txt` (sphinx, pytest-timeout). `requirements.txt` is untouched.
- `opencv-python-headless` only — the full wheel clashes with PySide6 on macOS.
- `Code.path_resource(...)` for all asset paths — never relative paths.
- Agentic / LLM-based automation is explicitly out of scope.

---

## 3. Terminology & Existing Infrastructure

See `docs/rpa/glossary.md` for the full glossary. Key terms for this spec:

| Term | Definition |
| --- | --- |
| **Activity** | A single unit of automation work — the UiPath-vocabulary equivalent of a single UI action with its precondition, postcondition, and compensation. |
| **Driver** | The seam between the runner and Qt. `Driver` is the plain base; `QtDriver` is the only Qt-touching implementation. |
| **Selector** | A descriptor that identifies a UI element across multiple tiers (object, image, OCR). |
| **Target** | A `Selector` plus optional anchor and timeout. |
| **State** | One of 8 recognised app states — the planner navigates between them. |
| **Snapshot** | A point-in-time read of the app: widget tree + optional screenshot. |
| **Runner** | The step-pumped state machine that executes a workflow's activities in the closed loop. |
| **Workflow** | An ordered list of activities with optional `RetryScope` / `Sequence` frames. |
| **Run** | One execution of a Workflow — has a `run_id`, a state, and a journal. |
| **FakeDriver** | The test double implementing the `Driver` interface over a `World` fixture. |
| **FakeClock** | The test double making `driver.now()` deterministic at zero wall-clock cost. |

---

## 4. Architecture

`bin/Code/Rpa/` is a flat package whose modules fall into three purity tiers:

```text
Tier 0 — dependency-free    Types.py, Errors.py
Tier 1 — stdlib only        Targets.py, Resolve.py, AppState.py, Journal.py
                             Activities.py, Runner.py, Fakes.py
Tier 2 — cv2/tesseract      Vision/{Availability,Template,Ocr,Manifest}.py
Tier 3 — Qt-touching        Driver.py (QtDriver), Vision/Capture.py, Service.py
```

The testability keystone: `Driver.py`, `Vision/Capture.py`, and `Service.py` are the only
modules that import PySide6. Everything else is pure Python. The `FakeClock` makes
retry/timeout/convergence logic deterministic at zero wall-clock cost.

---

## 5. Driver Contract

`Driver` is a plain base class raising `NotImplementedError`. Every method that touches Qt is
in `QtDriver`. `FakeDriver` provides a deterministic implementation over a `World` fixture.

Contract tests verify both `FakeDriver` and `QtDriver` override every method by reflecting over
`Driver.__dict__`.

### 5.1 Driver interface

| Member | Kind | Description |
| --- | --- | --- |
| `snapshot() → Snapshot` | method | Read app state. Fast; non-actuating. |
| `click(ref: ElementRef) → None` | method | Click a widget. Precondition: `ref` is valid. |
| `set_text(ref: ElementRef, text: str) → None` | method | Set text field value. |
| `select_combo(ref: ElementRef, value: str) → None` | method | Select combo item. |
| `trigger_action(name: str) → None` | method | Trigger a toolbar/menu action by name. |
| `now() → float` | method | Return current time in milliseconds. |
| `defer(fn, delay_ms: int) → None` | method | Schedule `fn` via Qt `singleShot`. |
| `capture() → Screenshot` | method | Capture main window as RGB ndarray. |

### 5.2 ElementRef semantics

`ElementRef(selector: Selector, rect: Rect)` — carries the selector that found it, never a Qt
pointer. `QtDriver` re-resolves the selector at actuation time and validates with
`shiboken6.isValid`, structurally eliminating the Qt use-after-free class.

---

## 6. Selector Model

`Selector(tier, cls, object_name, text, text_exact, role, scope, index, image, threshold)`.
`Target(selector, anchor, direction, max_distance, timeout_ms)`.

Two wire forms:
- **JSON** (primary): `json.loads(arg)` in `_dispatch` — no escaping issues.
- **Compact string** (debugging): `obj:cls=QLineEdit@right-of(obj:text=Player%20name)`.

Tier resolution order for `tier="auto"`: **object → image → OCR**. First at ≥ threshold wins.

Object-tier confidence: exact `object_name` = 1.00, exact text = 0.95, substring = 0.80,
class-only = 0.60.

When a non-object tier wins, `logger.warning` is emitted — a CV win means the object selector
is broken and should be fixed.

All coordinates are logical (DPR-1). `Screenshot.logical()` applies `cv2.resize` with
`INTER_AREA`.

---

## 7. State Model

Eight states, recognised from a single `Snapshot`, **dialog-first** priority:

`DIALOG_CONFIG → DIALOG_OTHER → GAME_OVER → ENGINE_THINKING → PLAYING → MANAGER_OTHER → HOME → UNKNOWN`

Transition data: `(source, target, name, cost, min_settle_ms, action, verify)`.

`StateGraph.plan()` uses **Dijkstra on cost**, not BFS. High-cost edges (e.g. `force_cancel`)
are avoided when cheaper paths exist.

Every `force_cancel` edge declares `min_settle_ms >= 600`. This is load-bearing: it matches
`_force_cancel()`'s deferred `proc.start(300ms)` comment documenting real C-level crashes.

Convergence re-plans from scratch after every transition — Terraform/Ansible idempotent style.

---

## 8. Runner State Machine

Run-level lifecycle: `PENDING → RUNNING → {SUCCEEDED, FAILED, CANCELLED, TIMED_OUT}`.
`CANCELLING` is a transient state reachable from `RUNNING` via `rpa_cancel`.

Per-step, 14 sub-states (canonical list — see `docs/rpa/state-machine.md` for the full spec):

```
STEP_ENTER  SETTLE_CONVERGE  DECIDE_RECOVERY  STEP_EXIT
CHECK_PRE   ACT              BACKOFF          FRAME_POP
CONVERGE    SETTLE           COMPENSATE       DONE
            VERIFY           UNWIND
```

The two invariants that govern the whole design:
1. **One pump = at most one sub-state transition and at most one driver actuation.**
2. **No `time.sleep()` anywhere** — all waiting is `now() >= deadline` polling.

Three independent deadlines (all in `driver.now()` terms):
- Run: 90 000 ms (`RUN_TIMEOUT_MS`)
- Step-verify: 5 000 ms (`VERIFY_TIMEOUT_MS`)
- Converge budget: 12 transitions (`CONVERGE_BUDGET`)

Backoff: `200 * 2**(n-1)` capped at 3 000 ms, ±10 % jitter from `random.Random(run_id)`.

Frame stack: `Sequence`/`RetryScope` frames carry `(activities, index, kind, attempts,
max_attempts, deadline, entry_state)`. A failed `retry` frame re-enters at `index=0,
attempts+1` — UiPath Retry Scope semantics with no recursion.

---

## 9. Vision

CV/OCR is a *fallback* location tier and a *verification* tier — never the primary assertion
where object tier works.

### 9.1 Capture pipeline

`QPixmap → QImage → ndarray`, handling `bytesPerLine()` row padding and ensuring RGB channel
order throughout. All `Vision/` code sees RGB; `cv2.imread` (BGR) is never used.

### 9.2 Template matching

`cv2.matchTemplate` with `TM_CCOEFF_NORMED`. Multi-scale fallback at `[0.95, 1.05, 0.90, 1.10]`
with `logger.warning` when a non-1.0 scale wins. NMS at IoU 0.3.

### 9.3 OCR

`pytesseract.image_to_data`. Multi-word phrases grouped by `(block, par, line)` with a sliding
window. 2× `INTER_CUBIC` upscale + grayscale preprocessing.

### 9.4 Availability

`Vision.Availability.probe()` is cached and never raises. Returns capability flags plus a `reason`
carrying the exact install command. `VisionUnavailableError.message` *is* the install command.

### 9.5 Templates manifest

`Resources/Rpa/Templates/manifest.json` — entries: `{name, path, dpr, theme, ui_mode,
translator, captured_at, sha256, width, height}`. Three cheap non-CV tests: manifest entries
exist, hashes match, workflow template refs are all in the manifest.

### 9.6 Reference captures

`Resources/Rpa/Reference/<name>.png` + `<name>.json` with assertions
`{templates_present, templates_absent, ocr_phrases_present, regions}`. The PNG is the
human-readable record; the JSON is what gets asserted. Never pixel-diffed (N-RPA-7).

---

## 10. Wire Protocol

Ten new verbs, all non-blocking, all taking a JSON object:

| Verb | Description |
| --- | --- |
| `rpa_capabilities` | CV/OCR availability flags and install hints |
| `rpa_state` | Current AppState name + recogniser evidence |
| `rpa_find` | Resolve a Target; return matching ElementRef(s) |
| `rpa_run` | Start a workflow; return `{run_id}` |
| `rpa_status` | Status of a run by `run_id` |
| `rpa_journal` | Full journal for a completed run |
| `rpa_cancel` | Cooperative cancellation; sets state to CANCELLING |
| `rpa_converge` | Start a convergence-only run to a target state |
| `rpa_act` | Start a single-activity run |
| `rpa_workflows` | List registered workflow names |

All read-only verbs (`rpa_state`, `rpa_find`, `rpa_status`, `rpa_journal`, `rpa_capabilities`,
`rpa_workflows`) are available during a run.

There is no `rpa_await` — waiting is client-side polling (`CaissaRpaClient.run_and_wait()`
polls `rpa_status` every 250 ms). This is the UiPath Orchestrator job+status model.

`rpa_cancel` is always accepted, including during an active run. `CANCELLING` routes through
`UNWIND` before reaching `CANCELLED` — compensations still run.

### 10.1 Concurrency rule

At most one run in `RUNNING`. A second `rpa_run`/`rpa_act`/`rpa_converge` while one is active
returns `RunAlreadyActiveError(active_run_id, current_sub_state)`.

### 10.2 `run_id` scheme

`r-<utc_yyyymmddThhmmss>-<4-hex>` — timestamp prefix makes retention a plain sort;
random suffix covers two runs in the same second.

---

## 11. Error Semantics

`CaissaError → RpaError → {specific errors}`. Plain base + one domain level. Specific types:

`DriverError`, `SelectorError`, `AmbiguousMatchError`, `TargetNotFoundError`,
`PreconditionError`, `PostconditionError`, `ConvergeError`, `RunAlreadyActiveError`,
`RunNotFoundError`, `WorkflowNotFoundError`, `VisionUnavailableError`, `ManifestError`,
`JournalError`, `StateError`, `RpaConfigError`.

All raise with a message identifying what failed, which value, and why if not obvious.
`raise … from exc` when wrapping lower-level exceptions. `logger.error(…, exc_info=True)`.

---

## 12. Non-Functional Constraints (N)

| ID | Constraint |
| --- | --- |
| N-RPA-1 | `Types.py` zero third-party imports |
| N-RPA-2 | PySide6 in `Driver.py`, `Vision/Capture.py`, `Service.py` only |
| N-RPA-3 | No `time.sleep()` anywhere |
| N-RPA-4 | `rpa_*` verbs < 200 ms while run active |
| N-RPA-5 | ≥ 90 % branch coverage on `Code.Rpa` (scoped omit list) |
| N-RPA-6 | RST docstrings on all callables |
| N-RPA-7 | No full-window pixel diffs — template-presence / OCR-location only |
| N-RPA-8 | No OS permissions needed — `widget.grab()` / `QTest`, not `pyautogui`/`mss` |
| N-RPA-9 | `cv2`/`numpy` absent from `sys.modules` after plain app start |
| N-RPA-10 | Run deadline 90 000 ms, at least 30 s below pytest timeout |

---

## 13. Classical Invariant Impact

**The RPA layer preserves the Classical Invariant absolutely.** It adds no widget, toolbar
entry, menu entry, mode JSON, QSS rule, overlay, or render-time config key that activates in
classical mode. The only always-on change is in `RemoteControl.py` (already ungated,
non-visual) and it is a pure delegation refactor gated by a 25-verb contract snapshot.

`bin/Code/Rpa/` is never imported until an `rpa_*` verb arrives (`CAISSA_RPA=0` disables
entirely). `Resources/Rpa/` is purely additive. `LogSetup.configure()` defaults to `WARNING`
with no console handler unless `CAISSA_LOG_LEVEL` is set.

**Positive enforcement:** `Workflows/classical_invariant.py` makes the Classical Invariant a
runnable regression check.

---

## 14. Implementation Sequence

See [feature_steps.md](feature_steps.md) for the phase-by-phase breakdown.

One branch = one phase = one PR. Phase order:

| # | Phase | Branch |
| --- | --- | --- |
| 0 | Documentation & process | `docs/rpa-layer` |
| 1 | Foundations | `chore/rpa-foundations` |
| 2 | Driver seam + contract lock | `refactor/rpa-driver-seam` |
| 3 | Targets + object resolver | `feat/rpa-targets` |
| 4 | State model | `feat/rpa-state-model` |
| 5 | Runner + journal + activities | `feat/rpa-runner` |
| 6 | Service + `rpa_*` verbs + client/CLI | `feat/rpa-service` |
| 7 | Vision | `feat/rpa-vision` |
| 8 | Workflows + regression suite | `feat/rpa-workflows` |
| 9 | Production readiness | `chore/rpa-production-readiness` |

---

## 15. Out of Scope

- Agentic / LLM-based automation
- Windows / Linux CI (proposed at Phase 9, not committed)
- i18n-sensitive selectors in v1 (D5 — deferred to v2)
- Remote / distributed automation
- Recording workflows from UI interaction

---

## 16. Changelog

| Date | Author | Change |
| --- | --- | --- |
| 2026-08-28 | Johannes Foulds / Claude | Initial spec — all R/I/P/Q/N sections |

---

## References

- `docs/rpa/` — product documentation
- `docs/rpa/state-machine.md` — formal state machine spec
- `docs/rpa/decisions.md` — ADR log (D1–D12)
- `bin/Code/Debug/RemoteControl.py` — the driver being wrapped
- `docs/standards/coding-standards.md`, `error-handling.md`
- `docs/ui-testing.md` §7.1 — amended CV policy
- [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119)
