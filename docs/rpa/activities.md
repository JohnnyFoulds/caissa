# Activities Catalogue

**Status:** Finalised against `bin/Code/Rpa/Activities.py` (Phase 5).  
**See also:** `docs/rpa/selectors.md` (targeting), `docs/rpa/state-machine.md` (execution contract)

---

## Overview

An **Activity** is one step in the closed-loop execution model.  Each activity declares:

- `name` — display name used in journals and logs
- `settle_ms` — how long to wait after `execute()` before polling `postcondition()`
- `max_attempts` — how many `ACT → VERIFY` cycles to attempt before entering recovery
- `compensable` — whether `compensate()` can undo the action
- `required_state` (optional) — the app state the runner must converge to before calling `precondition()`

The runner calls these hooks in order:

```
precondition(ctx)  →  execute(ctx)  →  postcondition(ctx)  →  prepare_next(ctx)
                                     ↑ postcondition can
                                       be polled many times
```

If postcondition fails, the runner optionally calls `compensate(ctx)`.

All activities live in `bin/Code/Rpa/Activities.py`.

---

## Base Class

### `Activity`

Plain base class (no ABC).  Raises `NotImplementedError` for `precondition`, `execute`, and
`postcondition`.  `compensate` and `prepare_next` have no-op defaults.

**Fields:**

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | `str` | `"Activity"` | Display name for journal + logs |
| `settle_ms` | `int` | `200` | ms to wait between execute and first verify poll |
| `max_attempts` | `int` | `1` | Max ACT→VERIFY cycles per runner step |
| `compensable` | `bool` | `False` | Whether `compensate()` is meaningful |
| `required_state` | `str \| None` | `None` | App state required before precondition |

**Methods:**

| Method | Signature | Raises | Notes |
|---|---|---|---|
| `precondition` | `(ctx) → bool` | `NotImplementedError` | Return True when the activity can execute |
| `execute` | `(ctx) → None` | `NotImplementedError` | Issue one driver actuation |
| `postcondition` | `(ctx) → bool` | `NotImplementedError` | Return True when the effect is observed |
| `compensate` | `(ctx) → None` | — | Undo the effect; no-op by default |
| `prepare_next` | `(ctx) → None` | — | Set up context for the next activity; no-op by default |

---

## Concrete Activities

### `Click`

Click a widget located by a `Selector`.

**UiPath analogue:** `Click Activity`

| Parameter | Type | Required |
|---|---|---|
| `selector` | `Selector` | Yes |
| `settle_ms` | `int` | No (default 200) |

**Precondition:** Target widget is found and visible.  
**Execute:** `ctx.driver.click(selector)`.  
**Postcondition:** Always True (fire-and-forget; use a subsequent `ElementExists` to verify if needed).

---

### `TypeInto`

Type text into a focused field.

**UiPath analogue:** `Type Into Activity`

| Parameter | Type | Required |
|---|---|---|
| `selector` | `Selector` | Yes |
| `text` | `str` | Yes |
| `clear_before` | `bool` | No (default True) |

**Precondition:** Target field is visible.  
**Execute:** Click field to focus, optionally clear, type text via `driver.set_field`.  
**Postcondition:** Always True.

---

### `SelectItem`

Choose an item in a combo box or list.

**UiPath analogue:** `Select Item Activity`

| Parameter | Type | Required |
|---|---|---|
| `selector` | `Selector` | Yes |
| `value` | `str` | Yes |

**Precondition:** Target combo/list is visible.  
**Execute:** `driver.combo_select(selector, value)`.  
**Postcondition:** Always True.

---

### `GetText`

Read the current text of a widget and store it in the context.

**UiPath analogue:** `Get Text Activity`

| Parameter | Type | Required |
|---|---|---|
| `selector` | `Selector` | Yes |
| `output_key` | `str` | Yes |

**Precondition:** Target widget is visible.  
**Execute:** `driver.get_field(selector)` → stored in `ctx.extra[output_key]`.  
**Postcondition:** `output_key` present and non-empty in `ctx.extra`.

---

### `ElementExists`

Assert that a widget matching a selector is currently visible.

**UiPath analogue:** `Element Exists Activity`

| Parameter | Type | Required |
|---|---|---|
| `selector` | `Selector` | Yes |
| `output_key` | `str` | No |
| `timeout_ms` | `int` | No (default 0 — single check) |

**Precondition:** Always True.  
**Execute:** No-op.  
**Postcondition:** Target widget found in current snapshot.

---

### `TakeScreenshot`

Capture the full window and save it to `ctx.run_dir/<filename>`.

**UiPath analogue:** `Take Screenshot Activity`

| Parameter | Type | Required |
|---|---|---|
| `filename` | `str` | Yes |

**Precondition:** Always True.  
**Execute:** `driver.screenshot()` → writes PNG.  
**Postcondition:** File exists at the expected path.

---

### `OpenConfig`

Open the General Configuration dialog.

**UiPath analogue:** `Open Application / Navigate To`

**Precondition:** App state is `HOME` (not already in a dialog).  
**Execute:** `driver.trigger_action("TB_OPTIONS")`.  
**Postcondition:** App state is `DIALOG_CONFIG`.  
**Compensate:** `driver.trigger_action("close_dialog")`.

---

### `CloseDialog`

Close the topmost modal dialog by clicking OK or pressing Escape.

**UiPath analogue:** `Close Application`

**Precondition:** App state is `DIALOG_CONFIG` or `DIALOG_OTHER`.  
**Execute:** `driver.trigger_action("close_dialog")`.  
**Postcondition:** App state is not a dialog.

---

### `SwitchTab`

Activate a named tab in the Configuration dialog.

| Parameter | Type | Required |
|---|---|---|
| `tab_name` | `str` | Yes |

**Precondition:** App state is `DIALOG_CONFIG`.  
**Execute:** `driver.click_tab(tab_name)`.  
**Postcondition:** Always True.

---

## Composite Activities

### `Sequence`

Execute a list of activities in order, as a nested frame.

**UiPath analogue:** `Sequence Container`

| Parameter | Type | Required |
|---|---|---|
| `activities` | `list[Activity]` | Yes |

The runner pushes a new `sequence` frame onto the stack.  When the frame is exhausted, it is
popped and the parent frame continues.  There is no retry at the Sequence level; individual
activities retry according to their own `max_attempts`.

---

### `RetryScope`

Execute a list of activities, retrying the entire body up to `max_attempts` times if any
activity fails.

**UiPath analogue:** `Retry Scope Activity`

| Parameter | Type | Required |
|---|---|---|
| `activities` | `list[Activity]` | Yes |
| `max_attempts` | `int` | No (default 3) |

The runner pushes a new `retry` frame onto the stack.  If any activity inside reaches
`DECIDE_RECOVERY` with no remaining retries, the runner checks whether the enclosing retry
frame has attempts remaining.  If so, it discards the failed inner activities, resets the
retry frame to `index=0, attempts+1`, and re-enters from the start of the body.

---

## Context

Activities receive a `Context` object.

```python
class Context:
    driver   # the Driver instance
    graph    # the StateGraph for convergence planning
    run_id   # the run identifier
    extra    # dict for workflow parameters and activity outputs
    snapshot # the most recent Snapshot (updated by refresh_snapshot())

    def refresh_snapshot(self) -> Snapshot:
        """Call driver.snapshot() and update self.snapshot."""
```

---

## Writing a Custom Activity

```python
class WaitForEngine(Activity):
    name = "WaitForEngine"
    settle_ms = 0
    max_attempts = 1

    def precondition(self, ctx) -> bool:
        snap = ctx.refresh_snapshot()
        return snap.state_name == PLAYING

    def execute(self, ctx) -> None:
        pass  # observation-only; no actuation

    def postcondition(self, ctx) -> bool:
        snap = ctx.refresh_snapshot()
        return snap.state_name != ENGINE_THINKING
```

Key rules:
- `execute()` issues **at most one driver actuation** — the runner enforces this by design.
- `postcondition()` must be **idempotent** — it is called multiple times per attempt.
- Never call `time.sleep()` — use `settle_ms` instead.
- Never import PySide6 — the rule `N-RPA-2` reserves Qt imports to `Driver.py`,
  `Vision/Capture.py`, and `Service.py`.
