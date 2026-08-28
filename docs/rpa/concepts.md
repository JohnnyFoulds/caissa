# RPA Layer — Concepts

**Status:** Living — updated as the design is implemented  
**Audience:** Anyone working with or extending the RPA layer  
**See also:** `docs/rpa/uipath-mapping.md` (UiPath equivalents), `docs/rpa/glossary.md` (terms)

---

## The Core Idea

The RPA layer formalises the 5-step closed loop that reliable UI automation requires:

1. **Before an action, check the app is in the expected state.**
2. **If not, drive the app to the expected state and GOTO 1.**
3. **Perform the action.**
4. **Verify the action performed and the expected state holds; if not, compensate or repair.**
5. **Prepare for the next action, GOTO 1.**

The loop is not aspirational. It is enforced mechanically by the `Runner` state machine — you
cannot skip a step, and you cannot proceed to step 3 until step 1 passes.

---

## The Six Building Blocks

### Driver

The seam between the runner and Qt. `Driver` is a plain base class; `QtDriver` is the only
implementation that actually touches widgets. `FakeDriver` is a test double that runs against
a `World` fixture — no Qt required.

All time, all scheduling, and all element acquisition go through the Driver. This is what
makes the entire retry/timeout/convergence logic testable at zero wall-clock cost.

### Target

A description of a UI element — not a reference to a live widget. `Target` wraps a `Selector`
(the matching criteria) with an optional anchor (directional context: "to the right of...").

There are three resolution tiers, tried in order:
- **Object tier** — Qt widget inspection via the existing RemoteControl infrastructure.
- **Image tier** — OpenCV template matching on a screen capture.
- **OCR tier** — Tesseract text location on a screen capture.

`Target` is evaluated lazily at actuation time, never at workflow authoring time. This is the
UiPath model and it is why RPA workflows are robust to app restarts.

### Activity

A single automation step. In UiPath terms, a single Activity. It has:
- `precondition(ctx)` — is the app in the right state for this action?
- `execute(ctx)` — perform the action (fast, non-blocking)
- `postcondition(ctx)` — did the action produce the expected result?
- `compensate(ctx)` — undo the action if postcondition never passed
- `prepare_next(ctx)` — any teardown before the next activity

The `Runner` enforces these contracts. You write activities; the runner enforces the loop.

### AppState

One of 8 recognised states the Caissa app can be in:

```
DIALOG_CONFIG  DIALOG_OTHER  GAME_OVER  ENGINE_THINKING
PLAYING  MANAGER_OTHER  HOME  UNKNOWN
```

Recognition is dialog-first: a modal dialog always overrides the background manager state.
The `StateGraph` holds the transitions between states and their costs. Dijkstra planning on
cost means the runner avoids dangerous high-cost transitions (like `force_cancel`) when a
cheaper path exists.

### Runner

The step-pumped state machine. It runs on its own QTimer — one `pump()` call every 50 ms.
Each pump does at most one sub-state transition and at most one driver actuation. It never
blocks the Qt main thread.

The `Runner` has 14 sub-states mapping the 5-step loop to concrete operations. See
`docs/rpa/state-machine.md` for the full formal spec.

### Workflow

An ordered list of activities, optionally grouped with `Sequence` and `RetryScope` frames.
Workflows are plain Python functions that return a list of `Activity` instances. There is no
XAML, no XML, no BPMN — just code.

```python
def my_workflow(params: dict) -> list[Activity]:
    return [
        Click(Target(Selector(cls="QPushButton", text="Play"))),
        AssertState("PLAYING"),
    ]
```

---

## The Closed Loop, Mechanically

```
For each Activity in the Workflow:
                                                    ┌──────────────────────┐
  STEP_ENTER ──► CHECK_PRE ──► ACT ──► VERIFY ──► STEP_EXIT              │
                    │                     │                                │
                    └── false ──► CONVERGE ──► SETTLE_CONVERGE ──┐       │
                    │                                              │       │
                    └──────────────────────────────────────────────┘       │
                                          │                                │
                                          └── timeout ──► DECIDE_RECOVERY │
                                                            │              │
                                                            ├── retry ──► BACKOFF ──┐
                                                            │                       │
                                                            └── compensate ─────────┘
                                                            │
                                                            └── unwind ──► DONE (FAILED)
```

Every box is a sub-state. Every pump advances one box.

---

## FakeDriver and Testability

`FakeDriver` is not a toy. It implements the full `Driver` interface over a `World` fixture —
a description of the app's widget tree in each known state, plus the transitions between
states. It is how you test:

- That an activity's precondition catches the right state
- That convergence routes correctly through the state graph
- That backoff behaves correctly under a deadline
- That compensation runs when postcondition exhausts retries

`FakeClock` makes all of these deterministic at zero wall-clock cost. A test loop is just:

```python
while runner.pump():
    clock.advance(50)   # advance by 50 ms per pump
    clock.run_due()     # fire any scheduled callbacks
```

`dry_run` mode uses `FakeDriver` to validate a workflow's selectors and state graph
**without a live Qt app**. It is a lint, not a full regression test — but it catches broken
selectors before you run the test suite.

---

## What Makes This Different from RemoteControl

`RemoteControl` is a driver — it knows how to click a button, but it has no opinion about
what state the app should be in before or after. It is a hammer.

The RPA layer is an engine — it checks preconditions, drives convergence, verifies
postconditions, and compensates when things go wrong. The hammer is now held by a hand that
knows how to use it and what to do when the nail bends.

The two coexist: `RemoteControl` still works exactly as before for its 25 original verbs.
The 10 new `rpa_*` verbs add the engine on top.
