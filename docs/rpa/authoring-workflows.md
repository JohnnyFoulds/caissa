# Authoring Workflows

**Status:** Finalised against Phase 8 (`feat/rpa-workflows`).  
**See also:** `docs/rpa/activities.md` (activity catalogue), `docs/rpa/concepts.md` (mental model)

A workflow is a named list of :class:`~Code.Rpa.Activities.Activity` instances that are
executed in sequence by the Runner.  This page explains how to write one.

---

## The minimal workflow

```python
# bin/Code/Rpa/Workflows/my_workflow.py
from Code.Rpa.Activities import Activity
from Code.Rpa.Workflows.Registry import register


class _DoSomething(Activity):
    name = "DoSomething"
    required_state = "HOME"
    settle_ms = 300
    max_attempts = 2

    def precondition(self, ctx) -> bool:
        from Code.Rpa.AppState import HOME, recognise
        return recognise(ctx.snapshot) == HOME

    def execute(self, ctx) -> None:
        ctx.driver.trigger_action("Options")

    def postcondition(self, ctx) -> bool:
        from Code.Rpa.AppState import DIALOG_CONFIG, recognise
        snap = ctx.refresh_snapshot()
        return recognise(snap) == DIALOG_CONFIG


register("my_workflow", [_DoSomething()])
```

Then add `"Code.Rpa.Workflows.my_workflow"` to `_load_builtin_workflows()` in
`bin/Code/Rpa/Service.py`.

---

## Registry API

```python
from Code.Rpa.Workflows.Registry import register, get, all_names

register("name", [activity1, activity2])   # register a workflow
activities = get("name")                   # raises WorkflowNotFoundError if unknown
names = all_names()                        # sorted list of registered names
```

`get()` returns a copy of the activity list so mutations do not affect the registry.

---

## Activity authoring rules

Each activity must implement:

| Method | When called | Return |
|---|---|---|
| `precondition(ctx)` | CHECK_PRE | `True` to proceed to ACT; `False` to trigger CONVERGE |
| `execute(ctx)` | ACT | nothing (side effect only) |
| `postcondition(ctx)` | VERIFY | `True` when the action succeeded |

Optional:

| Method/Attribute | Purpose |
|---|---|
| `compensate(ctx)` | Undo `execute` — only if `compensable = True` |
| `prepare_next(ctx)` | Update context between steps |
| `required_state` | State the Runner must converge to before CHECK_PRE |
| `settle_ms` | ms to wait after execute before VERIFY |
| `max_attempts` | Max ACT→VERIFY cycles before DECIDE_RECOVERY |
| `compensable` | Enable `compensate()` |

---

## Convergence

When `precondition` returns `False`, the Runner enters **CONVERGE** state.  It
uses `Dijkstra` on the `StateGraph` to plan the cheapest path from the current
state to `activity.required_state` (defaults to `"HOME"` if unset).

Each transition executes one driver action.  The planner replans from scratch
after every transition — if the app ends up in an unexpected state mid-plan, the
next pump corrects it automatically.

**Convergence budget** is 12 transitions per `CHECK_PRE` entry.  Budget
accumulates; it only resets on a new step, backoff, or compensate-retry.

---

## RetryScope

Use `RetryScope` to wrap a group of activities that should be retried as a unit:

```python
from Code.Rpa.Activities import RetryScope, Click, ElementExists

activities = [
    RetryScope([
        Click('{"object_name": "TB_OPTIONS"}'),
        ElementExists('{"object_name": "config_dialog"}'),
    ], max_attempts=3),
]
```

On failure, the Runner re-enters the `RetryScope` at index 0 with `attempts + 1`.
If all attempts fail the run unwinds.

---

## Using built-in activities

| Activity | Purpose |
|---|---|
| `Click(selector)` | Click a widget |
| `TypeInto(selector, value)` | Type text into a field |
| `SelectItem(selector, value)` | Select a combo box item |
| `GetText(selector, key)` | Read widget text into context |
| `ElementExists(selector, expected)` | Assert presence or absence |
| `TakeScreenshot(path, key)` | Capture a screenshot |
| `OpenConfig()` | Open the Configuration dialog |
| `CloseDialog()` | Close the topmost modal dialog |
| `SwitchTab(tab_text)` | Switch to a named tab |
| `Sequence(activities)` | Group without retry |
| `RetryScope(activities, max_attempts)` | Group with retry |

See `docs/rpa/activities.md` for the full catalogue with preconditions,
postconditions, compensation, and UiPath analogues.

---

## Selectors in activity arguments

Selectors can be passed as JSON strings or compact strings:

```python
# JSON
Click('{"cls": "QPushButton", "object_name": "TB_OPTIONS"}')

# Compact (object_name shorthand)
Click("obj:object_name=TB_OPTIONS")
```

Prefer `object_name` wherever the widget has one — it gives 1.00 confidence and
is stable across theme changes.  See `docs/rpa/selectors.md`.

---

## Workflow templates and the manifest

If your workflow uses image-tier selectors, the referenced template must be in the
manifest:

```json
{
    "name": "toolbar_options_button",
    "path": "Resources/Rpa/Templates/toolbar_options_button.png",
    "sha256": "...",
    "dpr": 1.0,
    ...
}
```

`test_every_workflow_template_ref_is_in_manifest` will catch any missing entries
at commit time.  See `docs/rpa/vision.md` for how to capture templates.

---

## Testing workflows

- **Unit tests** — test the Registry; mock the driver with `FakeDriver + FakeWorld`.
- **Integration tests** — marked `rpa_ui`; require a running Caissa process.

```bash
make test       # unit suite — runs Registry tests
make test-ui    # integration — runs rpa_ui suite (requires Caissa running)
```

The `rpa_ui` integration tests in `tests/ui/test_rpa_workflows.py` use
`CaissaRpaClient.run_and_wait()` to poll for completion.  They start and finish in
under 30 seconds for the smoke and invariant workflows.
