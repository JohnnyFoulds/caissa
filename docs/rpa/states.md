# App States — Reference

**Status:** Finalised against `bin/Code/Rpa/AppState.py` (Phase 4)  
**Implements:** `bin/Code/Rpa/AppState.py`  
**See also:** `docs/rpa/state-machine.md` (runner sub-states), `docs/rpa/concepts.md`

---

## The 8 States

Caissa can be in one of 8 mutually exclusive states. Every workflow starts by checking which
state the app is in; the runner navigates to the required state before an activity can act.

| State | Recogniser condition | Notes |
|---|---|---|
| `DIALOG_CONFIG` | A `WindowConfig` dialog is visible and active | Highest priority |
| `DIALOG_OTHER` | Any other modal dialog is visible | e.g. engine selection, error dialogs |
| `GAME_OVER` | Game manager visible; game is in terminal state | Waiting for new game |
| `ENGINE_THINKING` | Engine manager active; engine is calculating | No user actions possible |
| `PLAYING` | Engine manager active; waiting for player move | User can move |
| `MANAGER_OTHER` | A non-engine manager is active (training, analysis, etc.) | |
| `HOME` | No active game or dialog; main window toolbar visible | Default convergence target |
| `UNKNOWN` | None of the above match | Catch-all; always has a path to HOME |

Recognition is **dialog-first**: a modal dialog is always recognised before the background
manager state. This reflects the Qt modal stack — a dialog blocks all other actuation.

---

## Recognition Priority

```
recognise(snapshot):
    if any_modal_dialog_visible(snapshot):
        if is_config_dialog(snapshot): return DIALOG_CONFIG
        return DIALOG_OTHER
    if game_state_is_terminal(snapshot): return GAME_OVER
    if engine_is_thinking(snapshot):     return ENGINE_THINKING
    if engine_manager_active(snapshot):  return PLAYING
    if any_manager_active(snapshot):     return MANAGER_OTHER
    if at_home_screen(snapshot):         return HOME
    return UNKNOWN
```

### Recogniser signals

The recogniser reads the snapshot's `widget_tree` for these widget-info dict keys:

| Signal | Key/class | Notes |
|---|---|---|
| Modal dialog | `modal: True` OR `cls` contains `"Dialog"` or `"WindowConfig"` | |
| Config dialog | `cls == "WindowConfig"` OR `cls` contains `"OptionsDialog"/"ConfigDialog"` | |
| Game over | `game_over: True` OR `result` in `{1-0, 0-1, 1/2-1/2, draw, …}` | |
| Engine thinking | `engine_thinking: True` | |
| Engine manager | `cls == "ManagerPlayAgainstEngine"` OR `manager_class == "ManagerPlayAgainstEngine"` | |
| Any manager | `cls` contains `"Manager"` OR `manager_class` key present | |
| Home screen | `cls == "WBase"` OR `at_home: True` OR empty widget tree | |

These signals drive both the production recogniser (reading from `QtDriver.snapshot()`) and the
`FakeDriver` world fixture (which can set any of these flags directly).

---

## Transition Table

Transitions are data — they tell the `StateGraph` how to navigate between states.

| Source | Target | Name | Cost | min_settle_ms | Action |
|---|---|---|---|---|---|
| `DIALOG_CONFIG` | `HOME` | `dialog_cancel` | 1 | 100 | `driver.trigger_action("Cancel")` |
| `DIALOG_OTHER` | `HOME` | `dialog_cancel` | 1 | 100 | `driver.trigger_action("Cancel")` |
| `GAME_OVER` | `HOME` | `new_game_home` | 2 | 200 | `driver.trigger_action("Home")` |
| `ENGINE_THINKING` | `HOME` | `force_cancel` | 10 | 600 | `driver.trigger_action("ForceCancel")` |
| `PLAYING` | `HOME` | `force_cancel` | 10 | 600 | `driver.trigger_action("ForceCancel")` |
| `MANAGER_OTHER` | `HOME` | `force_cancel` | 10 | 600 | `driver.trigger_action("ForceCancel")` |
| `HOME` | `PLAYING` | `start_game` | 3 | 300 | `driver.trigger_action("Play")` |
| `HOME` | `DIALOG_CONFIG` | `open_config` | 1 | 100 | `driver.trigger_action("Options")` |
| `UNKNOWN` | `HOME` | `force_cancel` | 15 | 600 | `driver.trigger_action("ForceCancel")` |

> **Why force_cancel costs 10–15:** `_force_cancel()` in RemoteControl has comments documenting
> real Qt use-after-free C-level crashes. It is safe when done correctly (state set first,
> callbacks drained, `proc.start()` deferred 300 ms) but it is never the first choice.
> The high cost ensures Dijkstra routes through cheaper edges when they exist. When
> `min_settle_ms >= 600` is enforced by test, the runner always waits long enough for the
> deferred callback to land before issuing the next actuation.

---

## Convergence Rule

**The runner re-plans from scratch after every transition.** It never uses a stale plan.

This is the Terraform/Ansible idempotent convergence model: re-evaluate actual state, plan the
shortest path to desired state, execute one step. If the app goes somewhere unexpected, the
next pump picks it up and re-plans. The runner is not brittle about paths; it is only specific
about the goal state.

The convergence budget (12 transitions) prevents an infinite loop. Exhausting the budget
routes to `DECIDE_RECOVERY`.

---

## Invariant: Every State Can Reach HOME

Every state has a path (direct or via `UNKNOWN`) to `HOME`. This is the implicit precondition
of every workflow — a workflow that starts in any state can always converge.

`test_every_state_can_reach_home` asserts this for the StateGraph at Phase 4.
