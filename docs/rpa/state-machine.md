# Runner State Machine — Formal Specification

**Status:** Normative — design intent. Worked traces will be verified against real journals in Phase 5
(Gate H amends this document if they differ).  
**Implements:** `bin/Code/Rpa/Runner.py`  
**See also:** `docs/rpa/concepts.md` (the mental model), `docs/rpa/states.md` (app states)

---

## 1. Two-Level Model

The runner has two independent state machines.

### 1.1 Run-Level Lifecycle

```
PENDING ─── pump/start ──► RUNNING ─── success ──────────► SUCCEEDED
                              │
                              ├── run_deadline ────────────► TIMED_OUT
                              │
                              ├── rpa_cancel ──► CANCELLING
                              │                     │
                              │             unwind complete ─► CANCELLED
                              │
                              └── unrecoverable error ──────► FAILED
```

States:
- **PENDING** — `rpa_run` accepted; first pump not yet called
- **RUNNING** — pumps are being called; per-step sub-state machine is active
- **CANCELLING** — cooperative cancellation in progress; unwind is running
- **SUCCEEDED** — all activities completed their postconditions
- **FAILED** — an unrecoverable error terminated the run
- **CANCELLED** — `rpa_cancel` was honoured; compensations ran
- **TIMED_OUT** — `RUN_TIMEOUT_MS` (90 000 ms) elapsed; unwind ran

`CANCELLING` and deadline expiry both route through `UNWIND` — compensations run and the journal
is written before the run reaches a terminal state. This is why the run deadline must be at least
30 s below the pytest timeout (90 000 ms vs 120 000 ms): the process must not be killed before
the journal is persisted.

### 1.2 Cancellation Checks

Cancellation is cooperative. At the *entry* of every `pump()` call, the runner checks:
1. Is `_cancelling` set? → transition to `CANCELLING` immediately.
2. Is `now() >= run_deadline`? → transition to `CANCELLING` (terminal reason: `TIMED_OUT`).

At most one further actuation can be in flight when cancellation arrives.

---

## 2. Per-Step Sub-State Machine

### 2.1 The 14 Sub-States

This is the canonical enumeration. The `SubState` enum in `Runner.py` **MUST** have exactly
these members; `test_sub_state_enum_has_exactly_14_members` enforces it.

| # | Sub-State | Loop Step | May actuate? |
|---|---|---|---|
| 1 | `STEP_ENTER` | — | No |
| 2 | `CHECK_PRE` | Step 1 | No |
| 3 | `CONVERGE` | Step 2 | Yes (one per pump) |
| 4 | `SETTLE_CONVERGE` | Step 2 | No |
| 5 | `ACT` | Step 3 | Yes (once) |
| 6 | `SETTLE` | Step 3 | No |
| 7 | `VERIFY` | Step 4 | No |
| 8 | `DECIDE_RECOVERY` | Step 4 | No |
| 9 | `BACKOFF` | — | No |
| 10 | `COMPENSATE` | Step 4 | Yes (once) |
| 11 | `STEP_EXIT` | Step 5 | No |
| 12 | `FRAME_POP` | Step 5 | No |
| 13 | `UNWIND` | — | Yes (one per pump) |
| 14 | `DONE` | — | No (terminal) |

### 2.2 Complete Transition Table

One pump executes at most one transition from this table.

```
STEP_ENTER
  always ─────────────────────────────────────────────────► CHECK_PRE

CHECK_PRE  (read Snapshot; call activity.precondition(ctx))
  precondition true ──────────────────────────────────────► ACT
  precondition false ─────────────────────────────────────► CONVERGE

CONVERGE  (call graph.plan(current_state, required_state); execute ONE transition)
  plan non-empty, transition executed ────────────────────► SETTLE_CONVERGE
  plan empty (already at required state) ─────────────────► CHECK_PRE
  budget exhausted (12 transitions without reaching state) ► DECIDE_RECOVERY

SETTLE_CONVERGE  (idle; no actuation)
  now() >= actuated_at + transition.min_settle_ms ────────► CHECK_PRE

ACT  (call activity.execute(ctx); record actuated_at)
  always ─────────────────────────────────────────────────► SETTLE

SETTLE  (idle; no actuation)
  now() >= actuated_at + activity.settle_ms ──────────────► VERIFY

VERIFY  (call activity.postcondition(ctx) once per pump)
  postcondition true ─────────────────────────────────────► STEP_EXIT
  postcondition false, now() < verify_deadline ───────────► VERIFY (stay)
  postcondition false, now() >= verify_deadline ──────────► DECIDE_RECOVERY

DECIDE_RECOVERY  (inspect attempt count and compensability)
  attempts < max_attempts ────────────────────────────────► BACKOFF
  attempts >= max_attempts and activity.compensable ──────► COMPENSATE
  attempts >= max_attempts and not compensable ───────────► UNWIND

BACKOFF  (idle; no actuation)
  now() >= backoff_until ─────────────────────────────────► CHECK_PRE

COMPENSATE  (call activity.compensate(ctx); check recognise() == entry_state)
  back at entry_state ────────────────────────────────────► CHECK_PRE  (retry)
  not back at entry_state ────────────────────────────────► UNWIND

STEP_EXIT  (journal the step; call activity.prepare_next(ctx))
  frame has more activities ──────────────────────────────► STEP_ENTER
  frame exhausted ────────────────────────────────────────► FRAME_POP

FRAME_POP  (pop the current frame)
  stack non-empty ────────────────────────────────────────► STEP_EXIT (resume parent)
  stack empty ────────────────────────────────────────────► DONE → SUCCEEDED

UNWIND  (compensate executed steps in reverse; one per pump)
  steps remain ──────────────────────────────────────────► UNWIND (stay)
  all unwound ───────────────────────────────────────────► DONE → {FAILED, CANCELLED, TIMED_OUT}

DONE   (terminal; pump() returns False)
```

---

## 3. Mapping to the 5-Step Loop

| Your original step | Sub-states implementing it |
|---|---|
| 1. Before action, check app is in expected state | `CHECK_PRE` |
| 2. If not, get app to expected state and GOTO 1 | `CONVERGE` → `SETTLE_CONVERGE` → `CHECK_PRE` |
| 3. Perform action | `ACT` → `SETTLE` |
| 4. Verify action performed and state expected; if not, undo or fix | `VERIFY` → `DECIDE_RECOVERY` → (`BACKOFF` → `CHECK_PRE`) or `COMPENSATE` or `UNWIND` |
| 5. Prepare for next action, GOTO 1 | `STEP_EXIT` → `FRAME_POP` → next `STEP_ENTER` |

---

## 4. Invariants

Each invariant is named and pinned by the named test.

| Invariant | Test |
|---|---|
| One pump = at most one sub-state transition | `test_one_pump_one_transition_max` |
| One pump = at most one driver actuation | `test_one_pump_one_transition_max` |
| No `time.sleep()` anywhere | `test_no_sleep_call_anywhere` |
| All waiting is `now() >= deadline` polling | `test_settled_ms_not_pumps` |
| Convergence re-plans from scratch after each transition | `test_precondition_false_triggers_convergence` |
| No actuation before `min_settle_ms` elapses after a `force_cancel` transition | `test_every_force_cancel_edge_declares_min_settle_at_least_600` |
| `pump()` returns `False` once terminal | `test_happy_path_completes_to_succeeded` |

---

## 5. Three Deadlines

All in `driver.now()` terms (milliseconds since an arbitrary epoch, advancing with `FakeClock`).

| Deadline | Value | Named constant | Reset trigger |
|---|---|---|---|
| Run | 90 000 ms | `RUN_TIMEOUT_MS` | Never (set at run start) |
| Step-verify | 5 000 ms | `VERIFY_TIMEOUT_MS` | Each new attempt begins |
| Converge budget | 12 transitions | `CONVERGE_BUDGET` | Each `CHECK_PRE` entry |

The run deadline must satisfy `RUN_TIMEOUT_MS + 30_000 <= pytest_timeout_ms` (see D12).
`test_rpa_timeout_below_pytest_timeout` asserts this invariant numerically.

---

## 6. Backoff Formula

```
backoff_ms = min(200 * 2**(attempt - 1), 3000) * jitter
jitter     = uniform(0.9, 1.1) from random.Random(run_id)
```

`random.Random(run_id)` makes backoff deterministic for a given run — a failed run can be
replayed by feeding the same `run_id` to `FakeDriver`.

---

## 7. Frame Stack

`Sequence` and `RetryScope` push a `Frame` onto the stack:

```
Frame(activities, index, kind, attempts, max_attempts, deadline, entry_state)
```

When a `retry` frame's body fails (reaches `DECIDE_RECOVERY` with `attempts < max_attempts`):
- `BACKOFF` idles
- `CHECK_PRE` re-enters the frame at `index=0, attempts+1`
- This is UiPath Retry Scope semantics with no nesting and no blocking

When a `retry` frame exhausts its `max_attempts`:
- The recovery path (`COMPENSATE` or `UNWIND`) unwinds the frame

The frame stack makes scoping without recursion possible: `pump()` is a flat loop.

---

## 8. Worked Traces

These are design-intent traces. Phase 5 verifies them against real journals; Gate H amends
this document if any trace is wrong.

### 8.1 Happy Path: Click toolbar button

| Pump | Sub-state | What happens | Actuates? |
|---|---|---|---|
| 1 | STEP_ENTER | Pop `Click(toolbar, "Options")` off frame | No |
| 2 | CHECK_PRE | Snapshot reads state=HOME; precondition: state==HOME ✓ | No |
| 3 | ACT | `driver.trigger_action("Options")` | Yes |
| 4 | SETTLE | `now() < actuated_at + 100` — wait | No |
| 5 | SETTLE | `now() >= actuated_at + 100` | No |
| 6 | VERIFY | Snapshot: DIALOG_CONFIG present → postcondition ✓ | No |
| 7 | STEP_EXIT | Journal step; prepare_next | No |
| 8 | FRAME_POP | Frame exhausted; stack empty | No |
| 9 | DONE | → SUCCEEDED | No |

### 8.2 Precondition failure + convergence + recovery

| Pump | Sub-state | What happens |
|---|---|---|
| 1 | STEP_ENTER | Pop `Click(btn)` off frame; required_state=HOME |
| 2 | CHECK_PRE | State=DIALOG_OTHER → precondition false |
| 3 | CONVERGE | plan(DIALOG_OTHER → HOME): execute `dialog_cancel` transition |
| 4 | SETTLE_CONVERGE | Wait `min_settle_ms` for dialog dismiss |
| 5 | SETTLE_CONVERGE | Elapsed; back to CHECK_PRE |
| 6 | CHECK_PRE | State=HOME → precondition true |
| 7 | ACT | `driver.click(btn)` |
| 8..N | SETTLE → VERIFY | Postcondition false × 3 pumps (button slow) |
| N+1 | VERIFY | Postcondition true |
| N+2 | STEP_EXIT → FRAME_POP → DONE | → SUCCEEDED |

### 8.3 Postcondition exhaustion + compensation + unwind

| Pump | Sub-state | What happens |
|---|---|---|
| 1-3 | STEP_ENTER → ACT → SETTLE | Activity executed |
| 4..N | VERIFY | Postcondition false until `verify_deadline` |
| N+1 | DECIDE_RECOVERY | `attempts == max_attempts`, compensable=True |
| N+2 | COMPENSATE | `activity.compensate(ctx)`; check state == entry_state |
| N+3 | CHECK_PRE | Compensate succeeded; retry the step (attempts+1) |
| ... | VERIFY again | Postcondition still fails |
| M | DECIDE_RECOVERY | `attempts == max_attempts` again, compensable=False now |
| M+1 | UNWIND | Walk executed steps in reverse, compensating one per pump |
| ... | UNWIND | All steps unwound |
| K | DONE | → FAILED |

---

## 9. Journal Format

The journal records every sub-state entry in a bounded trace (500 entries max).

```json
{
  "run_id": "r-20260828T142233-9f1c",
  "workflow": "config_roundtrip",
  "terminal_status": "SUCCEEDED",
  "started_at_ms": 1724850000000,
  "ended_at_ms": 1724850012345,
  "total_pumps": 47,
  "env": {
    "dpr": 2.0,
    "theme": "By default",
    "ui_mode": "classical",
    "translator": "en",
    "cv_available": false,
    "ocr_available": false,
    "cv_version": null,
    "caissa_version": "0.8.0"
  },
  "steps": [
    {
      "activity": "Click",
      "attempt": 1,
      "pre_state": "HOME",
      "post_state": "DIALOG_CONFIG",
      "converge_transitions": [],
      "winning_tier": "object",
      "confidence": 0.95,
      "pumps": 9,
      "error": null
    }
  ],
  "sub_state_trace": ["STEP_ENTER", "CHECK_PRE", "ACT", "SETTLE", "VERIFY", "STEP_EXIT", "..."]
}
```

The `env` block is written at run-start and captures the runtime context. It is what makes a
failed CV run diagnosable six weeks later. `winning_tier` and `confidence` tell you which
resolution tier found the element for each step.
