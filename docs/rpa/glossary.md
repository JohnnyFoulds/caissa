# Glossary

Terms used in the Caissa RPA layer, with UiPath synonyms where applicable.

---

| Term | Definition | UiPath synonym |
|---|---|---|
| **Activity** | A single automation step with precondition, execute, postcondition, and compensation methods. | Activity |
| **Anchor** | A directional relationship between two elements: "locate X relative to Y". Used when a target element has no reliable discriminating selector of its own. | Anchor / "Relative To" in CV scope |
| **AppState** | One of 8 recognised states the Caissa app can be in (see `docs/rpa/states.md`). | — |
| **Backoff** | An idle period between retry attempts; duration grows exponentially, capped at 3 000 ms. | — |
| **Budget (converge)** | The maximum number of state transitions the runner may execute while trying to reach the required state for a single activity (12). | — |
| **CaissaError** | The repo-wide base exception class for all Caissa-specific errors. Lives in `bin/Code/Rpa/Errors.py`. | — |
| **Compensation** | The undo action for an activity — what to do when the postcondition never passes. Reverses the effect of `execute`. | Compensation handler / Try/Catch/Finally |
| **Context (`ctx`)** | The mutable bundle passed to every activity method: `run_id`, `driver`, `snapshot`, `params`, `frame_path`. | — |
| **Convergence** | Automatic navigation from the current state to the required state via the StateGraph. | — |
| **Driver** | The seam between the runner and Qt. `Driver` (plain base), `QtDriver` (Qt-touching), `FakeDriver` (test double). | Robot |
| **DPR** | Device Pixel Ratio — the scaling factor between physical and logical pixels on HiDPI/Retina displays. Templates are stored at DPR-1 (logical) resolution. | — |
| **dry_run** | Execute a workflow using `FakeDriver` against a `World` fixture — validates selectors and state graph without a live app. | — |
| **ElementRef** | A located element: carries the `Selector` that found it plus its logical `Rect`. Never a Qt pointer. | — |
| **FakeClock** | A test double for `driver.now()` and `driver.defer()` — makes timing deterministic at zero wall-clock cost. | — |
| **FakeDriver** | A test double for `Driver` that operates over a `World` fixture. Powers `dry_run` and unit tests. | — |
| **Frame** | An entry on the runner's frame stack — either a `Sequence` or `RetryScope`. | — |
| **Journal** | The structured record of a run: every step, every sub-state trace, the env block, and the terminal status. Persisted to `UserData/RpaRuns/<run_id>/journal.json`. | Log / Report |
| **Logical coordinates** | Pixel coordinates at DPR-1 scale. All `Rect` values are in logical coordinates. | — |
| **NMS** | Non-Maximum Suppression — removes duplicate template match hits that overlap at IoU > 0.3. | — |
| **Postcondition** | What must be true after an activity's `execute` method. Verified by polling until the step-verify deadline. | Assertion / assertion handler |
| **Precondition** | What must be true before an activity can be executed. Checked at `CHECK_PRE`; convergence runs if it fails. | Guard condition |
| **Pump** | One call to `Runner.pump()`. Executes at most one sub-state transition and at most one driver actuation. | — |
| **RetryScope** | A frame that re-enters its body (at `index=0`) on failure up to `max_attempts` times. | Retry Scope |
| **RpaError** | The domain base exception for the RPA layer; inherits from `CaissaError`. | — |
| **Run** | A single execution of a Workflow with a unique `run_id`, a run-level state, and a journal. | Job |
| **run_id** | Unique identifier for a run — format `r-<utc_yyyymmddThhmmss>-<4-hex>`. | Job ID |
| **Runner** | The step-pumped state machine that executes a workflow's activities in the closed loop. | Robot / Executor |
| **Selector** | A descriptor identifying a UI element: tier, class, object name, text, role, scope, etc. | Selector |
| **Sequence** | A frame that executes a list of activities in order; fail-fast on any step. | Sequence |
| **Snapshot** | A point-in-time read of the app state: state name, widget tree, optional screenshot. | — |
| **StateGraph** | The graph of `Transition` objects; `plan()` runs Dijkstra to find the minimum-cost path. | — |
| **Target** | A `Selector` plus optional anchor, direction, max_distance, and timeout. The full element specification passed to an activity. | Target / UI element |
| **Tier** | The resolution mechanism: `object` (widget inspection), `image` (template matching), `ocr` (text location), or `auto` (try object first). | — |
| **Transition** | A directed edge in the StateGraph: source state, target state, action, cost, and `min_settle_ms`. | — |
| **Unwind** | Reverse-order compensating execution of all steps in the current workflow when an unrecoverable failure occurs. | Saga rollback / compensating transactions |
| **Workflow** | An ordered list of activities (Python function returning `list[Activity]`). | Workflow / Process |
| **World** | The fixture that seeds `FakeDriver`: describes the widget tree at each known app state and the effects of each transition. | — |
