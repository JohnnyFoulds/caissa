# Runner State Machine — Formal Specification

**Status:** Normative — finalised against `Runner.py` Phase 5. Worked traces verified by the Phase 5
unit test suite; this document was amended from design intent to match actual behaviour.  
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

DECIDE_RECOVERY  (inspect attempt count, compensability, and frame stack)
  attempts > 0 and attempts < max_attempts ────────────────► BACKOFF
  attempts >= max_attempts and compensable, first time ────► COMPENSATE
  no retries available, retry frame in stack with room ────► STEP_ENTER (frame re-entry)
  otherwise ───────────────────────────────────────────────► UNWIND

  Notes:
  - BACKOFF requires at least one ACT call (attempts > 0).  A convergence failure
    (budget exhausted before any ACT) routes to compensation or unwind, not backoff.
  - COMPENSATE is tried at most once per step (_step_compensated flag).  If the step
    fails again after the compensated retry, the run goes to UNWIND — not COMPENSATE
    again.  This prevents infinite compensate→retry loops.
  - RetryScope frames are checked by walking the stack outward.  The innermost retry
    frame with attempts < max_attempts absorbs the failure; all inner frames are
    discarded and the retry frame resets to index=0, attempts+1.

BACKOFF  (idle; no actuation)
  now() >= backoff_until ─────────────────────────────────► CHECK_PRE  (converge count reset)

COMPENSATE  (call activity.compensate(ctx); check recognise() == entry_state)
  back at entry_state ────────────────────────────────────► CHECK_PRE  (retry; converge count reset)
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
| Step-verify | 5 000 ms | `VERIFY_TIMEOUT_MS` | Each new ACT call (new attempt) |
| Converge budget | 12 transitions | `CONVERGE_BUDGET` | New step, backoff retry, or compensate retry |

Note: the converge budget is **not** reset on every `CHECK_PRE` entry.  It accumulates across
`CONVERGE → SETTLE_CONVERGE → CHECK_PRE` cycles within the same step attempt.  It only resets
when a new step begins (`STEP_ENTER`), when backoff transitions to `CHECK_PRE`, or when a
successful compensation retries the step.

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

When `DECIDE_RECOVERY` runs and no activity-level retries are available, the runner walks the
frame stack outward.  The innermost `retry` frame with `attempts < max_attempts` absorbs the
failure: all inner frames are discarded, the retry frame resets to `index=0, attempts+1`,
and the sub-state returns to `STEP_ENTER`.  This is UiPath Retry Scope semantics — no nesting,
no blocking.

When all retry frames are exhausted (or there are none), the run enters `UNWIND`.

The frame stack makes scoping without recursion possible: `pump()` is a flat loop.

---

## 8. Worked Traces

Verified against the Phase 5 unit test suite (`tests/unit/rpa/test_runner.py`).

### 8.1 Happy Path

Single `OkActivity` (precondition=True, postcondition=True, settle_ms=0).

| Pump | Status before | Sub-state | What happens |
|---|---|---|---|
| 1 | PENDING | STEP_ENTER | Transitions to RUNNING; sets run deadline; no sub-state work |
| 2 | RUNNING | STEP_ENTER | Pops OkActivity; creates StepRecord; → CHECK_PRE |
| 3 | RUNNING | CHECK_PRE | Refreshes snapshot; precondition() → True; → ACT |
| 4 | RUNNING | ACT | execute() called; _step_attempts=1; → SETTLE |
| 5 | RUNNING | SETTLE | settle_ms=0, already elapsed; → VERIFY |
| 6 | RUNNING | VERIFY | postcondition() → True; → STEP_EXIT |
| 7 | RUNNING | STEP_EXIT | Journal step; frame.advance(); frame exhausted → FRAME_POP |
| 8 | RUNNING | FRAME_POP | Stack empty; → DONE; _terminate(SUCCEEDED) |
| 9 | SUCCEEDED | — | pump() returns False |

### 8.2 Precondition failure → convergence

Activity with `required_state=PLAYING`; FakeDriver world transitions HOME→PLAYING on
the `new_game_home` action.

| Pump | Sub-state | What happens |
|---|---|---|
| 1 | STEP_ENTER | PENDING→RUNNING (first pump) |
| 2 | STEP_ENTER | Pops activity; → CHECK_PRE; _step_converge_count=0 |
| 3 | CHECK_PRE | State=HOME ≠ PLAYING → precondition false; → CONVERGE |
| 4 | CONVERGE | plan(HOME→PLAYING): trigger `new_game_home`; _converge_count=1; → SETTLE_CONVERGE |
| 5 | SETTLE_CONVERGE | Idle until min_settle_ms elapsed |
| … | SETTLE_CONVERGE | (pumps with clock.advance) |
| N | SETTLE_CONVERGE | Elapsed; → CHECK_PRE |
| N+1 | CHECK_PRE | State=PLAYING; precondition() → True; → ACT |
| N+2 | ACT | execute(); → SETTLE → VERIFY |
| N+3 | VERIFY | postcondition() → True; → STEP_EXIT → FRAME_POP → DONE → SUCCEEDED |

### 8.3 Converge budget exhaustion

Activity whose `required_state` is unreachable (no path in the graph).

| Pump | Sub-state | What happens |
|---|---|---|
| 1 | STEP_ENTER | PENDING→RUNNING |
| 2 | STEP_ENTER | Pops activity; → CHECK_PRE |
| 3 | CHECK_PRE | precondition false; → CONVERGE |
| 4 | CONVERGE | plan() raises ConvergeError (no path); → DECIDE_RECOVERY |
| 5 | DECIDE_RECOVERY | _step_attempts=0 (no ACT yet); not compensable; no retry frame; → UNWIND |
| 6 | UNWIND | _executed_steps empty; → DONE; _terminate(FAILED) |
| 7 | FAILED | pump() returns False |

When the planner _can_ reach the target but the world never changes:
the converge budget (12 transitions) is exhausted across successive
CONVERGE → SETTLE_CONVERGE → CHECK_PRE cycles without the precondition
ever becoming true.  After 12 transitions, CONVERGE → DECIDE_RECOVERY
as above.

### 8.4 Postcondition failure + single compensation + unwind

`CompensableActivity` (max_attempts=1, compensable=True, postcondition always False).

| Pump | Sub-state | What happens |
|---|---|---|
| 1–2 | STEP_ENTER → CHECK_PRE | precondition True; → ACT |
| 3 | ACT | execute(); _step_attempts=1; → SETTLE → VERIFY |
| 4..N | VERIFY | postcondition False; polling until verify_deadline |
| N+1 | DECIDE_RECOVERY | attempts(1)==max_attempts(1); compensable and not yet compensated; → COMPENSATE; _step_compensated=True |
| N+2 | COMPENSATE | compensate(); check state==entry_state; matches → CHECK_PRE; _step_converge_count=0 |
| N+3 | CHECK_PRE | precondition True; → ACT |
| N+4 | ACT | execute(); _step_attempts=2; → SETTLE → VERIFY |
| N+4..M | VERIFY | postcondition False again |
| M+1 | DECIDE_RECOVERY | attempts>=max_attempts; compensable but _step_compensated=True; no retry frame; → UNWIND |
| M+2 | UNWIND | Walk executed steps in reverse (compensating any compensable ones) |
| … | UNWIND | All steps processed |
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
