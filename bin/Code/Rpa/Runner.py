"""
bin/Code/Rpa/Runner.py — Step-pumped closed-loop state machine.

The runner executes an ordered list of activities in the 5-step closed loop.  Each
call to :meth:`Runner.pump` advances the machine by **at most one sub-state
transition** and issues **at most one driver actuation**.  The caller is responsible
for calling ``pump`` on a QTimer (see ``Service.py``) or in a test loop
``while runner.pump(): clock.advance(50); clock.run_due()``.

Three independent deadlines, all in ``driver.now()`` terms:

- **Run deadline** — :data:`RUN_TIMEOUT_MS` (90 000 ms). Exhausting it routes through
  UNWIND so the journal is written before the run terminates.
- **Step-verify deadline** — :data:`VERIFY_TIMEOUT_MS` (5 000 ms per attempt).
- **Converge budget** — :data:`CONVERGE_BUDGET` (12 transitions per ``CHECK_PRE``
  entry).

Backoff: ``200 * 2**(attempt-1)`` capped at 3 000 ms, ±10 % jitter from
``random.Random(run_id)`` — deterministic for a given run_id.

:spec: FR-2, NFR-3, NFR-10, §8 (feature_spec.md); `docs/rpa/state-machine.md`
"""

from __future__ import annotations

import dataclasses
import enum
import logging
import random
from typing import Any

from Code.Rpa.Activities import Activity, Context, RetryScope, Sequence
from Code.Rpa.AppState import DEFAULT_GRAPH, HOME, StateGraph, recognise
from Code.Rpa.Errors import ConvergeError
from Code.Rpa.Journal import Journal, RunRecord, StepRecord
from Code.Rpa.Types import Snapshot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------

RUN_TIMEOUT_MS: int = 90_000
"""Run deadline in milliseconds. Must be ≥ 30 000 ms below pytest timeout (D12)."""

VERIFY_TIMEOUT_MS: int = 5_000
"""Per-step verify timeout in milliseconds; reset for each new attempt."""

CONVERGE_BUDGET: int = 12
"""Maximum transitions before the runner gives up converging and enters recovery."""

_MAX_BACKOFF_MS: int = 3_000
_BACKOFF_BASE_MS: int = 200


# ---------------------------------------------------------------------------
# Run-level status
# ---------------------------------------------------------------------------

class RunStatus(str, enum.Enum):
    """Run-level lifecycle states."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


_TERMINAL_STATUSES: frozenset[RunStatus] = frozenset({
    RunStatus.SUCCEEDED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
    RunStatus.TIMED_OUT,
})


# ---------------------------------------------------------------------------
# Per-step sub-states
# ---------------------------------------------------------------------------

class SubState(enum.Enum):
    """Per-step sub-state machine states.

    Exactly 14 members — ``test_sub_state_enum_has_exactly_14_members`` enforces this.
    The canonical list and transition table are in ``docs/rpa/state-machine.md §2``.
    """

    STEP_ENTER = "STEP_ENTER"
    CHECK_PRE = "CHECK_PRE"
    CONVERGE = "CONVERGE"
    SETTLE_CONVERGE = "SETTLE_CONVERGE"
    ACT = "ACT"
    SETTLE = "SETTLE"
    VERIFY = "VERIFY"
    DECIDE_RECOVERY = "DECIDE_RECOVERY"
    BACKOFF = "BACKOFF"
    COMPENSATE = "COMPENSATE"
    STEP_EXIT = "STEP_EXIT"
    FRAME_POP = "FRAME_POP"
    UNWIND = "UNWIND"
    DONE = "DONE"


# ---------------------------------------------------------------------------
# Frame stack
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Frame:
    """A scope frame on the runner's frame stack.

    :param activities: Ordered list of activities in this frame.
    :param index: Next activity to execute (0-based).
    :param kind: ``"sequence"`` or ``"retry"``.
    :param attempts: Number of completed retry cycles (0 for sequence frames).
    :param max_attempts: Maximum retry cycles (ignored for sequence frames).
    :param entry_state: App state at frame entry (used to verify compensation success).
    """

    activities: list[Activity]
    index: int = 0
    kind: str = "sequence"
    attempts: int = 0
    max_attempts: int = 1
    entry_state: str = HOME

    def current_activity(self) -> Activity | None:
        """Return the current activity or None if the frame is exhausted.

        :returns: The next activity to run, or None.
        """
        if self.index < len(self.activities):
            return self.activities[self.index]
        return None

    def advance(self) -> None:
        """Move to the next activity in this frame.

        :returns: None.
        """
        self.index += 1

    def is_exhausted(self) -> bool:
        """Return True if all activities in this frame have been completed.

        :returns: True when index >= len(activities).
        """
        return self.index >= len(self.activities)

    def reset(self) -> None:
        """Reset to the first activity (for retry re-entry).

        :returns: None.
        """
        self.index = 0
        self.attempts += 1


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class Runner:
    """Step-pumped closed-loop state machine executing a list of :class:`~Code.Rpa.Activities.Activity` objects.

    Instantiate with a driver, a list of top-level activities, and a ``run_id``.
    Call :meth:`pump` in a loop or on a QTimer.  It returns ``False`` once the run
    reaches a terminal state.

    :param driver: The driver instance.
    :param activities: Top-level activities to execute.
    :param run_id: Unique run identifier (used for journal and backoff RNG).
    :param graph: State graph for convergence.  Defaults to :data:`~Code.Rpa.AppState.DEFAULT_GRAPH`.
    :param workflow_name: Workflow name stored in the journal.
    :param run_dir: Directory for the journal.  ``None`` skips persistence.
    :param extra: Optional workflow parameters passed to :class:`~Code.Rpa.Activities.Context`.
    """

    def __init__(
        self,
        driver,
        activities: list[Activity],
        run_id: str,
        graph: StateGraph | None = None,
        workflow_name: str = "unnamed",
        run_dir: str | None = None,
        extra: dict | None = None,
    ) -> None:
        """Initialise the runner.

        :param driver: Driver instance.
        :param activities: Top-level activities.
        :param run_id: Run identifier.
        :param graph: StateGraph for convergence; defaults to DEFAULT_GRAPH.
        :param workflow_name: Workflow name for the journal.
        :param run_dir: Journal output directory; None skips persistence.
        :param extra: Optional workflow parameters.
        """
        self._driver = driver
        self._run_id = run_id
        self._workflow_name = workflow_name
        self._run_dir = run_dir
        self._graph = graph or DEFAULT_GRAPH
        self._ctx = Context(driver=driver, graph=self._graph, run_id=run_id, extra=extra)
        self._rng = random.Random(run_id)

        # Frame stack — start with a single sequence frame for top-level activities
        self._stack: list[Frame] = [Frame(activities=list(activities), kind="sequence")]

        # Sub-state machine
        self._sub_state: SubState = SubState.STEP_ENTER
        self._run_status: RunStatus = RunStatus.PENDING
        self._cancelling: bool = False
        self._cancel_reason: RunStatus = RunStatus.FAILED

        # Per-step tracking
        self._step_record: StepRecord | None = None
        self._step_index: int = 0
        self._step_entry_snapshot: Snapshot | None = None
        self._step_attempts: int = 0
        self._step_converge_count: int = 0
        self._step_compensated: bool = False  # prevent double-compensation loops
        self._actuated_at: float = 0.0
        self._verify_deadline: float = 0.0
        self._backoff_until: float = 0.0
        self._pumping: bool = False  # re-entrancy guard

        # Unwind stack — executed steps in order, compensated in reverse
        self._executed_steps: list[tuple[Activity, StepRecord]] = []
        self._unwind_index: int = 0

        # Run-level timing
        self._run_start_ms: float = 0.0
        self._run_deadline: float = 0.0
        self._total_pumps: int = 0

        # Journal record
        self._run_record = RunRecord(
            run_id=run_id,
            workflow_name=workflow_name,
            status=RunStatus.PENDING.value,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def run_status(self) -> RunStatus:
        """Current run-level status.

        :returns: :class:`RunStatus` enum member.
        """
        return self._run_status

    def cancel(self) -> None:
        """Request cooperative cancellation.

        The run will finish the current actuation and then unwind.  Safe to call
        from any thread.

        :returns: None.
        """
        self._cancelling = True
        logger.debug("[%s] cancel requested", self._run_id)

    def pump(self) -> bool:
        """Advance the state machine by at most one sub-state transition.

        :returns: ``True`` if the run is still active; ``False`` if terminal.
        :raises RuntimeError: If called re-entrantly.
        """
        # Terminal check
        if self._run_status in _TERMINAL_STATUSES:
            return False

        # Re-entrancy guard
        if self._pumping:
            logger.warning("[%s] pump() re-entered — ignoring", self._run_id)
            return True
        self._pumping = True

        try:
            return self._do_pump()
        finally:
            self._pumping = False

    # ------------------------------------------------------------------
    # Internal pump logic
    # ------------------------------------------------------------------

    def _do_pump(self) -> bool:
        """Execute one sub-state transition."""
        now = self._driver.now()
        self._total_pumps += 1

        # First pump: transition PENDING → RUNNING and set run deadline
        if self._run_status == RunStatus.PENDING:
            self._run_status = RunStatus.RUNNING
            self._run_start_ms = now
            self._run_deadline = now + RUN_TIMEOUT_MS
            self._run_record.created_at_ms = now
            self._run_record.status = RunStatus.RUNNING.value
            logger.debug("[%s] run started (deadline at now+%d ms)", self._run_id, RUN_TIMEOUT_MS)

        # Check cancellation / deadline at every pump entry — but do NOT re-enter
        # UNWIND if we are already unwinding (that would reset the unwind index).
        if (self._cancelling or now >= self._run_deadline) and self._sub_state not in (
            SubState.UNWIND, SubState.DONE
        ):
            if not self._cancelling:
                self._cancelling = True
                self._cancel_reason = RunStatus.TIMED_OUT
                logger.debug("[%s] run deadline exceeded", self._run_id)
            else:
                self._cancel_reason = RunStatus.CANCELLED
            self._run_status = RunStatus.CANCELLING
            self._enter_unwind()
            return True

        sub = self._sub_state
        logger.debug("[%s] pump sub_state=%s", self._run_id, sub.value)

        if sub == SubState.STEP_ENTER:
            self._on_step_enter(now)
        elif sub == SubState.CHECK_PRE:
            self._on_check_pre(now)
        elif sub == SubState.CONVERGE:
            self._on_converge(now)
        elif sub == SubState.SETTLE_CONVERGE:
            self._on_settle_converge(now)
        elif sub == SubState.ACT:
            self._on_act(now)
        elif sub == SubState.SETTLE:
            self._on_settle(now)
        elif sub == SubState.VERIFY:
            self._on_verify(now)
        elif sub == SubState.DECIDE_RECOVERY:
            self._on_decide_recovery(now)
        elif sub == SubState.BACKOFF:
            self._on_backoff(now)
        elif sub == SubState.COMPENSATE:
            self._on_compensate(now)
        elif sub == SubState.STEP_EXIT:
            self._on_step_exit(now)
        elif sub == SubState.FRAME_POP:
            self._on_frame_pop(now)
        elif sub == SubState.UNWIND:
            self._on_unwind(now)
        elif sub == SubState.DONE:
            return False

        # Record sub-state in step record
        if self._step_record is not None:
            self._step_record.record_sub_state(sub.value)
            self._step_record.pumps += 1

        return self._run_status not in _TERMINAL_STATUSES

    # ------------------------------------------------------------------
    # Sub-state handlers
    # ------------------------------------------------------------------

    def _on_step_enter(self, now: float) -> None:
        """Enter a new step: pop the current activity from the frame."""
        frame = self._current_frame()
        if frame is None:
            # No frame — nothing to do; fall through to DONE
            self._sub_state = SubState.FRAME_POP
            return

        activity = frame.current_activity()
        if activity is None:
            self._sub_state = SubState.FRAME_POP
            return

        # Handle Sequence/RetryScope by pushing a new frame
        if isinstance(activity, Sequence):
            frame.advance()
            self._stack.append(Frame(
                activities=list(activity.activities),
                kind="sequence",
                entry_state=self._ctx.snapshot.state_name if self._ctx.snapshot else HOME,
            ))
            self._sub_state = SubState.STEP_ENTER
            return

        if isinstance(activity, RetryScope):
            frame.advance()
            self._stack.append(Frame(
                activities=list(activity.activities),
                kind="retry",
                max_attempts=activity.max_attempts,
                entry_state=self._ctx.snapshot.state_name if self._ctx.snapshot else HOME,
            ))
            self._sub_state = SubState.STEP_ENTER
            return

        # Normal activity
        self._step_record = StepRecord(
            index=self._step_index,
            activity_name=activity.name,
            entry_state=self._ctx.snapshot.state_name if self._ctx.snapshot else HOME,
        )
        self._step_attempts = 0
        self._step_converge_count = 0
        self._step_compensated = False
        self._sub_state = SubState.CHECK_PRE

    def _on_check_pre(self, now: float) -> None:
        """Refresh snapshot and check precondition."""
        snap = self._ctx.refresh_snapshot()

        frame = self._current_frame()
        activity = frame.current_activity() if frame else None
        if activity is None:
            self._sub_state = SubState.FRAME_POP
            return

        try:
            result = activity.precondition(self._ctx)
        except Exception as exc:
            logger.error("[%s] precondition raised: %s", self._run_id, exc, exc_info=True)
            result = False

        if result:
            self._sub_state = SubState.ACT
        else:
            self._sub_state = SubState.CONVERGE

    def _on_converge(self, now: float) -> None:
        """Execute one convergence transition toward the required state."""
        frame = self._current_frame()
        activity = frame.current_activity() if frame else None
        if activity is None:
            self._sub_state = SubState.FRAME_POP
            return

        snap = self._ctx.snapshot
        current_state = recognise(snap) if snap else HOME
        required = getattr(activity, "required_state", None) or HOME

        if self._step_converge_count >= CONVERGE_BUDGET:
            logger.warning(
                "[%s] converge budget exhausted (%d/%d) for %r",
                self._run_id, self._step_converge_count, CONVERGE_BUDGET, activity.name,
            )
            self._sub_state = SubState.DECIDE_RECOVERY
            return

        if current_state == required:
            # Already there — re-check precondition
            self._sub_state = SubState.CHECK_PRE
            return

        try:
            path = self._graph.plan(current_state, required)
        except ConvergeError as exc:
            logger.warning("[%s] no path to %r: %s", self._run_id, required, exc)
            self._sub_state = SubState.DECIDE_RECOVERY
            return

        if not path:
            self._sub_state = SubState.CHECK_PRE
            return

        transition = path[0]
        logger.debug(
            "[%s] converge: executing transition %r", self._run_id, transition.name
        )
        if transition.action:
            self._driver.trigger_action(transition.action)
        self._actuated_at = now
        self._step_converge_count += 1
        # Record settle duration from the transition
        self._pending_converge_settle_ms = transition.min_settle_ms
        self._sub_state = SubState.SETTLE_CONVERGE

    def _on_settle_converge(self, now: float) -> None:
        """Idle until the converge settle window has elapsed."""
        settle_ms = getattr(self, "_pending_converge_settle_ms", 100)
        if now >= self._actuated_at + settle_ms:
            self._sub_state = SubState.CHECK_PRE

    def _on_act(self, now: float) -> None:
        """Execute the activity."""
        frame = self._current_frame()
        activity = frame.current_activity() if frame else None
        if activity is None:
            self._sub_state = SubState.FRAME_POP
            return

        self._step_attempts += 1
        if self._step_record:
            self._step_record.attempts = self._step_attempts

        try:
            activity.execute(self._ctx)
        except Exception as exc:
            logger.error("[%s] execute raised: %s", self._run_id, exc, exc_info=True)
            if self._step_record:
                self._step_record.error = str(exc)

        self._actuated_at = now
        self._verify_deadline = now + VERIFY_TIMEOUT_MS
        self._sub_state = SubState.SETTLE

    def _on_settle(self, now: float) -> None:
        """Idle until the activity's settle window has elapsed."""
        frame = self._current_frame()
        activity = frame.current_activity() if frame else None
        settle = getattr(activity, "settle_ms", 200) if activity else 200
        if now >= self._actuated_at + settle:
            self._sub_state = SubState.VERIFY

    def _on_verify(self, now: float) -> None:
        """Check the postcondition once per pump."""
        frame = self._current_frame()
        activity = frame.current_activity() if frame else None
        if activity is None:
            self._sub_state = SubState.FRAME_POP
            return

        try:
            result = activity.postcondition(self._ctx)
        except Exception as exc:
            logger.error("[%s] postcondition raised: %s", self._run_id, exc, exc_info=True)
            result = False

        if result:
            self._sub_state = SubState.STEP_EXIT
        elif now >= self._verify_deadline:
            logger.debug(
                "[%s] verify deadline exceeded for %r", self._run_id, activity.name
            )
            self._sub_state = SubState.DECIDE_RECOVERY
        # else: stay in VERIFY

    def _on_decide_recovery(self, now: float) -> None:
        """Choose the recovery path: backoff, compensate, retry-scope, or unwind."""
        frame = self._current_frame()
        activity = frame.current_activity() if frame else None
        max_attempts = getattr(activity, "max_attempts", 1) if activity else 1

        if self._step_attempts > 0 and self._step_attempts < max_attempts:
            # More retries available for this activity (only after at least one execution)
            delay = min(
                _BACKOFF_BASE_MS * (2 ** (self._step_attempts - 1)),
                _MAX_BACKOFF_MS,
            )
            jitter = self._rng.uniform(0.9, 1.1)
            self._backoff_until = now + delay * jitter
            logger.debug(
                "[%s] backing off %.0f ms (attempt %d/%d)",
                self._run_id, delay * jitter, self._step_attempts, max_attempts,
            )
            self._sub_state = SubState.BACKOFF
        elif getattr(activity, "compensable", False) and not self._step_compensated:
            # Compensate once; if the step fails again after the retry, unwind
            self._step_compensated = True
            self._sub_state = SubState.COMPENSATE
        else:
            # Check if a surrounding RetryScope frame can absorb this failure
            for i in range(len(self._stack) - 1, -1, -1):
                rf = self._stack[i]
                if rf.kind == "retry" and rf.attempts < rf.max_attempts:
                    # Pop all frames above the retry frame, reset it
                    del self._stack[i + 1:]
                    rf.reset()
                    self._step_converge_count = 0
                    self._step_compensated = False
                    self._sub_state = SubState.STEP_ENTER
                    logger.debug(
                        "[%s] retry-scope re-entry (attempt %d/%d)",
                        self._run_id, rf.attempts, rf.max_attempts,
                    )
                    return
            self._enter_unwind()

    def _on_backoff(self, now: float) -> None:
        """Idle until the backoff window has elapsed, then retry."""
        if now >= self._backoff_until:
            self._step_converge_count = 0  # fresh converge budget for the new attempt
            self._sub_state = SubState.CHECK_PRE

    def _on_compensate(self, now: float) -> None:
        """Execute compensation and check if we're back at entry state."""
        frame = self._current_frame()
        activity = frame.current_activity() if frame else None
        if activity is None:
            self._enter_unwind()
            return

        try:
            activity.compensate(self._ctx)
        except Exception as exc:
            logger.error("[%s] compensate raised: %s", self._run_id, exc, exc_info=True)
            self._enter_unwind()
            return

        snap = self._ctx.refresh_snapshot()
        current_state = recognise(snap)
        entry_state = self._step_record.entry_state if self._step_record else HOME
        if current_state == entry_state:
            logger.debug("[%s] compensate succeeded; retrying step", self._run_id)
            self._step_converge_count = 0  # fresh converge budget for the retry
            self._sub_state = SubState.CHECK_PRE
        else:
            logger.debug(
                "[%s] compensate: state %r != entry %r; unwinding",
                self._run_id, current_state, entry_state,
            )
            self._enter_unwind()

    def _on_step_exit(self, now: float) -> None:
        """Journal this step and advance to the next."""
        frame = self._current_frame()
        activity = frame.current_activity() if frame else None

        if self._step_record:
            self._step_record.result = "ok"
            self._step_record.exit_state = (
                recognise(self._ctx.snapshot) if self._ctx.snapshot else HOME
            )
            self._step_record.duration_ms = now - self._run_record.created_at_ms
            self._run_record.steps.append(self._step_record)

        if activity is not None:
            self._executed_steps.append((activity, self._step_record or StepRecord(
                index=self._step_index, activity_name="?", entry_state=HOME
            )))
            activity.prepare_next(self._ctx)

        self._step_index += 1
        self._step_record = None

        if frame:
            frame.advance()

        if frame and frame.is_exhausted():
            self._sub_state = SubState.FRAME_POP
        else:
            self._sub_state = SubState.STEP_ENTER

    def _on_frame_pop(self, now: float) -> None:
        """Pop the current frame; resume parent or complete."""
        if self._stack:
            frame = self._stack[-1]
            if frame.is_exhausted():
                self._stack.pop()

        if not self._stack:
            # All frames exhausted — succeeded
            self._sub_state = SubState.DONE
            self._terminate(RunStatus.SUCCEEDED, now)
        else:
            # Resume parent frame
            self._sub_state = SubState.STEP_ENTER

    def _on_unwind(self, now: float) -> None:
        """Compensate one executed step per pump, in reverse."""
        if self._unwind_index < len(self._executed_steps):
            reverse_index = len(self._executed_steps) - 1 - self._unwind_index
            activity, step_rec = self._executed_steps[reverse_index]
            self._unwind_index += 1
            if getattr(activity, "compensable", False):
                try:
                    activity.compensate(self._ctx)
                except Exception as exc:
                    logger.error(
                        "[%s] unwind compensate raised: %s", self._run_id, exc, exc_info=True
                    )
        else:
            # Unwind complete
            self._sub_state = SubState.DONE
            self._terminate(self._cancel_reason, now)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_frame(self) -> Frame | None:
        """Return the top frame or None if the stack is empty.

        :returns: Top :class:`Frame` or None.
        """
        return self._stack[-1] if self._stack else None

    def _enter_unwind(self) -> None:
        """Transition to UNWIND mode.

        :returns: None.
        """
        self._sub_state = SubState.UNWIND
        self._unwind_index = 0
        if self._step_record:
            self._step_record.result = "failed"
            self._run_record.steps.append(self._step_record)
            self._step_record = None

    def _terminate(self, status: RunStatus, now: float) -> None:
        """Mark the run as terminated and persist the journal.

        :param status: Terminal run status.
        :param now: Current time in milliseconds.
        :returns: None.
        """
        self._run_status = status
        self._run_record.status = status.value
        self._run_record.total_pumps = self._total_pumps
        self._run_record.completed_at_ms = now
        logger.info("[%s] run terminated: %s", self._run_id, status.value)

        if self._run_dir:
            try:
                Journal.persist(self._run_record, self._run_dir)
            except Exception as exc:
                logger.error(
                    "[%s] failed to write journal: %s", self._run_id, exc, exc_info=True
                )
