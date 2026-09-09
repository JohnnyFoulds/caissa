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

Plain base class (no ABC).  Raises `NotImplementedError` for `precondition`, `execute`,
`postcondition` **and `compensate`** — only `prepare_next` has a no-op default.
(`OpenConfig` is currently the only built-in activity that overrides `compensate`.)

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
| `compensate` | `(ctx) → None` | `NotImplementedError` unless overridden | Undo the effect; only when `compensable` is True |
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

**Class attrs:** `settle_ms = 200` (per-instance via ctor), `max_attempts = 3`.  
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
| `value` | `str` | Yes |

**Class attrs:** `settle_ms = 100`, `max_attempts = 2`.  
**Precondition:** Target field is visible.  
**Execute:** `ctx.driver.set_text(selector, value)`.  
**Postcondition:** Always True.

---

### `SelectItem`

Choose an item in a combo box or list.

**UiPath analogue:** `Select Item Activity`

| Parameter | Type | Required |
|---|---|---|
| `selector` | `Selector` | Yes |
| `value` | `str` | Yes |

**Class attrs:** `settle_ms = 100`, `max_attempts = 2`.  
**Precondition:** Target combo/list is visible.  
**Execute:** `ctx.driver.select_combo(selector, value)`.  
**Postcondition:** Always True.

---

### `GetText`

Read the current text of a widget and store it in the context.

**UiPath analogue:** `Get Text Activity`

| Parameter | Type | Required |
|---|---|---|
| `selector` | `Selector` | Yes |
| `key` | `str` | No (default `"text"`) |

**Class attrs:** `settle_ms = 0`, `max_attempts = 1`.  
**Precondition:** A widget with matching `object_name` is visible.  
**Execute:** Reads the text from the current snapshot → stored in `ctx.extra[key]`
(no driver call — snapshot-tier read).  
**Postcondition:** `key` present in `ctx.extra`.

---

### `ElementExists`

Assert that a widget matching a selector is currently visible.

**UiPath analogue:** `Element Exists Activity`

| Parameter | Type | Required |
|---|---|---|
| `selector` | `Selector` | Yes |
| `expected` | `bool` | No (default True — must exist; False = must be absent) |

**Class attrs:** `settle_ms = 0`, `max_attempts = 1`.  
**Precondition:** Always True.  
**Execute:** Records presence from the current snapshot (no driver call).  
**Postcondition:** Presence matches `expected` (`found == expected`).

---

### `TakeScreenshot`

Capture the full window and save it to `ctx.run_dir/<filename>`.

**UiPath analogue:** `Take Screenshot Activity`

| Parameter | Type | Required |
|---|---|---|
| `path` | `str` | Yes |
| `key` | `str` | No (default `"screenshot"`) |

**Class attrs:** `settle_ms = 0`, `max_attempts = 1`.  
**Precondition:** Always True.  
**Execute:** `ctx.driver.capture(path)` → return value stored in `ctx.extra[key]`.  
**Postcondition:** `key` present in `ctx.extra`.

---

### `OpenConfig`

Open the General Configuration dialog.

**UiPath analogue:** `Open Application / Navigate To`

**Class attrs:** `settle_ms = 300`, `max_attempts = 2`, `compensable = True`,
`required_state = "HOME"`.  
**Precondition:** App state is `HOME` (not already in a dialog).  
**Execute:** `ctx.driver.trigger_action("Options")`.  
**Postcondition:** App state is `DIALOG_CONFIG`.  
**Compensate:** `ctx.driver.trigger_action("Cancel")`.

---

### `CloseDialog`

Close the topmost modal dialog via Cancel.

**UiPath analogue:** `Close Application`

**Class attrs:** `settle_ms = 150`, `max_attempts = 2`.  
**Precondition:** App state is `DIALOG_CONFIG` or `DIALOG_OTHER`.  
**Execute:** `ctx.driver.trigger_action("Cancel")`.  
**Postcondition:** App state is not a dialog.

---

### `SwitchTab`

Activate a named tab in the Configuration dialog.

| Parameter | Type | Required |
|---|---|---|
| `tab_text` | `str` | Yes |

**Class attrs:** `settle_ms = 100`, `max_attempts = 2`.  
**Precondition:** Always True — the click is attempted and the result is not verified.  
**Execute:** `ctx.driver.trigger_action(f"tab:{tab_text}")`.  
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
    run_dir  # journal output directory (None skips persistence)
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
  The eight driver verbs are `snapshot`, `click`, `set_text`, `select_combo`,
  `trigger_action`, `now`, `defer`, `capture`.
- `postcondition()` must be **idempotent** — it is called multiple times per attempt.
- Never call `time.sleep()` — use `settle_ms` instead.
- Never import PySide6 — the rule `N-RPA-2` reserves Qt imports to `Driver.py`,
  `Vision/Capture.py`, and `Service.py`.
