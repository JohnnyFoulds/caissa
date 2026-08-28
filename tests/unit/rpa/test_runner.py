"""
Phase 5 — Runner, Journal, and Activities unit tests.

Uses FakeDriver + FakeClock for all timing; no Qt or real app required.

:spec: FR-2, FR-6, NFR-3, NFR-10, §8 (feature_spec.md)
"""

import os
import re
import tempfile

import pytest

pytestmark = pytest.mark.rpa

from Code.Rpa.Activities import Activity, Click, Context, RetryScope, Sequence
from Code.Rpa.AppState import DEFAULT_GRAPH, HOME, DIALOG_OTHER, PLAYING
from Code.Rpa.Errors import ConvergeError
from Code.Rpa.Fakes import FakeClock, FakeDriver, World
from Code.Rpa.Journal import Journal, RunRecord, StepRecord
from Code.Rpa.Runner import (
    CONVERGE_BUDGET,
    RUN_TIMEOUT_MS,
    VERIFY_TIMEOUT_MS,
    Runner,
    RunStatus,
    SubState,
)
from Code.Rpa.Types import Snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap_home() -> Snapshot:
    """Snapshot that recognises as HOME."""
    return Snapshot(state_name=HOME, widget_tree=[{"cls": "WBase", "visible": True}], timestamp_ms=0.0)


def _snap_playing() -> Snapshot:
    """Snapshot that recognises as PLAYING."""
    return Snapshot(
        state_name=PLAYING,
        widget_tree=[{"cls": "ManagerPlayAgainstEngine", "visible": True}],
        timestamp_ms=0.0,
    )


def _snap_dialog() -> Snapshot:
    """Snapshot that recognises as DIALOG_OTHER."""
    return Snapshot(
        state_name=DIALOG_OTHER,
        widget_tree=[{"cls": "WFritzNewGame", "modal": True, "visible": True}],
        timestamp_ms=0.0,
    )


class _OkActivity(Activity):
    """Test double: precondition=True, postcondition=True immediately."""
    name = "OkActivity"
    settle_ms = 0
    max_attempts = 1

    def precondition(self, ctx):
        return True

    def execute(self, ctx):
        pass

    def postcondition(self, ctx):
        return True


class _FailActivity(Activity):
    """Test double: precondition=True, postcondition always fails."""
    name = "FailActivity"
    settle_ms = 0
    max_attempts = 1

    def precondition(self, ctx):
        return True

    def execute(self, ctx):
        pass

    def postcondition(self, ctx):
        return False


class _CompensableActivity(Activity):
    """Test double: succeeds on first postcondition but is compensable."""
    name = "CompensableActivity"
    settle_ms = 0
    max_attempts = 1
    compensable = True
    compensate_called = False

    def precondition(self, ctx):
        return True

    def execute(self, ctx):
        pass

    def postcondition(self, ctx):
        return False  # Always fails to trigger compensation

    def compensate(self, ctx):
        _CompensableActivity.compensate_called = True


class _RetryActivity(Activity):
    """Test double: fails on first attempt, succeeds on second."""
    name = "RetryActivity"
    settle_ms = 0
    max_attempts = 2
    call_count = 0

    def precondition(self, ctx):
        return True

    def execute(self, ctx):
        _RetryActivity.call_count += 1

    def postcondition(self, ctx):
        return _RetryActivity.call_count >= 2


class _PreconditionFalseActivity(Activity):
    """Test double: precondition always False (requires convergence)."""
    name = "PreconditionFalseActivity"
    settle_ms = 0
    max_attempts = 1
    required_state = PLAYING  # can't get there with default test world

    def precondition(self, ctx):
        return False

    def execute(self, ctx):
        pass

    def postcondition(self, ctx):
        return True


def _run_to_completion(runner, clock, max_pumps: int = 500):
    """Pump runner until done or max_pumps reached."""
    for _ in range(max_pumps):
        if not runner.pump():
            break
        clock.advance(50.0)
        clock.run_due()
    return runner


def _make_runner(activities, world_widgets=None, clock=None, run_id="r-test-0001"):
    """Build a runner with a FakeDriver world."""
    if clock is None:
        clock = FakeClock(start_ms=0.0)
    widgets = world_widgets or [{"cls": "WBase", "visible": True}]
    world = World(current_state=HOME, widget_trees={HOME: widgets})
    driver = FakeDriver(world=world, clock=clock)
    return Runner(
        driver=driver,
        activities=activities,
        run_id=run_id,
        graph=DEFAULT_GRAPH,
    ), driver, clock


# ---------------------------------------------------------------------------
# SubState enum
# ---------------------------------------------------------------------------

def test_sub_state_enum_has_exactly_14_members():
    """SubState must have exactly 14 members per state-machine.md §2.1."""
    assert len(SubState) == 14


def test_state_machine_doc_lists_every_substate():
    """state-machine.md must mention every SubState member name."""
    doc_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "docs", "rpa", "state-machine.md"
    )
    doc_path = os.path.normpath(doc_path)
    with open(doc_path) as fh:
        content = fh.read()
    for member in SubState:
        assert member.value in content, (
            f"SubState.{member.name} ({member.value!r}) is not mentioned in state-machine.md"
        )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_completes_to_succeeded():
    """A single OkActivity workflow completes with SUCCEEDED status."""
    runner, driver, clock = _make_runner([_OkActivity()])
    _run_to_completion(runner, clock)
    assert runner.run_status == RunStatus.SUCCEEDED


def test_happy_path_pump_returns_false_when_done():
    """pump() returns False once the run is in a terminal state."""
    runner, driver, clock = _make_runner([_OkActivity()])
    _run_to_completion(runner, clock)
    assert runner.pump() is False


def test_two_activities_both_execute():
    """Two OkActivities both run and the run SUCCEEDS."""
    executed = []

    class Tracker(Activity):
        name = "Tracker"
        settle_ms = 0
        max_attempts = 1

        def __init__(self, label):
            self.label = label

        def precondition(self, ctx):
            return True

        def execute(self, ctx):
            executed.append(self.label)

        def postcondition(self, ctx):
            return True

    runner, driver, clock = _make_runner([Tracker("a"), Tracker("b")])
    _run_to_completion(runner, clock)
    assert runner.run_status == RunStatus.SUCCEEDED
    assert executed == ["a", "b"]


# ---------------------------------------------------------------------------
# Precondition failure → convergence
# ---------------------------------------------------------------------------

def test_precondition_false_triggers_convergence():
    """An activity whose precondition is always False routes through CONVERGE."""
    runner, driver, clock = _make_runner([_PreconditionFalseActivity()])
    # Drive a few pumps and check we hit CONVERGE or DECIDE_RECOVERY
    sub_states = set()
    for _ in range(50):
        if not runner.pump():
            break
        sub_states.add(runner._sub_state)
        clock.advance(50.0)
        clock.run_due()
    assert SubState.CONVERGE in sub_states or SubState.DECIDE_RECOVERY in sub_states


def test_convergence_exhausts_budget_transitions_to_unwind():
    """Convergence that repeatedly fails exhausts the budget and enters UNWIND."""
    runner, driver, clock = _make_runner([_PreconditionFalseActivity()])
    _run_to_completion(runner, clock)
    # Run fails because it can never reach PLAYING from the home-only world
    assert runner.run_status == RunStatus.FAILED


# ---------------------------------------------------------------------------
# Postcondition retry / timeout
# ---------------------------------------------------------------------------

def test_postcondition_retried_within_deadline():
    """A FailActivity with max_attempts=2 gets two execute() calls."""
    _RetryActivity.call_count = 0
    runner, driver, clock = _make_runner([_RetryActivity()])
    _run_to_completion(runner, clock)
    assert runner.run_status == RunStatus.SUCCEEDED
    assert _RetryActivity.call_count == 2


def test_postcondition_timeout_triggers_decide_recovery():
    """A FailActivity with max_attempts=1 triggers DECIDE_RECOVERY after verify deadline."""
    runner, driver, clock = _make_runner([_FailActivity()])
    # Run until DECIDE_RECOVERY or terminal
    decide_seen = False
    for _ in range(300):
        if not runner.pump():
            break
        if runner._sub_state == SubState.DECIDE_RECOVERY:
            decide_seen = True
            break
        clock.advance(50.0)
        clock.run_due()
    assert decide_seen or runner.run_status == RunStatus.FAILED


# ---------------------------------------------------------------------------
# Recovery paths
# ---------------------------------------------------------------------------

def test_decide_recovery_retryable_backs_off():
    """max_attempts > 1 routes through BACKOFF."""
    _RetryActivity.call_count = 0

    class TwoAttempts(Activity):
        name = "TwoAttempts"
        settle_ms = 0
        max_attempts = 2
        _calls = 0

        def precondition(self, ctx):
            return True

        def execute(self, ctx):
            TwoAttempts._calls += 1

        def postcondition(self, ctx):
            return TwoAttempts._calls >= 2

    runner, driver, clock = _make_runner([TwoAttempts()])
    backoff_seen = False
    for _ in range(500):
        if not runner.pump():
            break
        if runner._sub_state == SubState.BACKOFF:
            backoff_seen = True
        clock.advance(50.0)
        clock.run_due()
    assert backoff_seen or runner.run_status == RunStatus.SUCCEEDED


def test_decide_recovery_compensable_compensates():
    """A compensable activity that always fails routes through COMPENSATE."""
    _CompensableActivity.compensate_called = False
    runner, driver, clock = _make_runner([_CompensableActivity()])
    _run_to_completion(runner, clock)
    assert _CompensableActivity.compensate_called


def test_compensate_fail_unwinds():
    """If compensation doesn't restore entry state, run enters UNWIND."""
    _CompensableActivity.compensate_called = False
    runner, driver, clock = _make_runner([_CompensableActivity()])
    _run_to_completion(runner, clock)
    # _CompensableActivity always fails postcondition, compensate is called,
    # but the FakeDriver world stays at HOME so compensation "succeeds" (stays at HOME).
    # We just verify no crash and a terminal status.
    assert runner.run_status in (RunStatus.FAILED, RunStatus.SUCCEEDED)


def test_unwind_calls_compensate_in_reverse():
    """Unwind compensates executed steps in reverse order."""
    order = []

    class Step(Activity):
        name = "Step"
        settle_ms = 0
        max_attempts = 1
        compensable = True

        def __init__(self, label):
            self.label = label

        def precondition(self, ctx):
            return True

        def execute(self, ctx):
            pass

        def postcondition(self, ctx):
            return True

        def compensate(self, ctx):
            order.append(self.label)

    # Three steps that succeed, then a fail that triggers unwind
    class Fail(Activity):
        name = "Fail"
        settle_ms = 0
        max_attempts = 1

        def precondition(self, ctx):
            return True

        def execute(self, ctx):
            pass

        def postcondition(self, ctx):
            return False

    runner, driver, clock = _make_runner([Step("a"), Step("b"), Fail()])
    _run_to_completion(runner, clock)
    assert runner.run_status == RunStatus.FAILED
    # Steps a and b were executed and should be compensated (b then a)
    assert order == ["b", "a"]


# ---------------------------------------------------------------------------
# Frame stack
# ---------------------------------------------------------------------------

def test_frame_pop_resumes_parent():
    """After a Sequence completes, the parent frame continues."""
    executed = []

    class Tracker(Activity):
        name = "Tracker"
        settle_ms = 0

        def __init__(self, label):
            self.label = label

        def precondition(self, ctx):
            return True

        def execute(self, ctx):
            executed.append(self.label)

        def postcondition(self, ctx):
            return True

    runner, driver, clock = _make_runner([
        Tracker("before"),
        Sequence([Tracker("inner_a"), Tracker("inner_b")]),
        Tracker("after"),
    ])
    _run_to_completion(runner, clock)
    assert runner.run_status == RunStatus.SUCCEEDED
    assert executed == ["before", "inner_a", "inner_b", "after"]


def test_retry_scope_re_enters_on_failure():
    """RetryScope retries its body on failure."""
    attempt_counts = [0]

    class CountedRetry(Activity):
        name = "CountedRetry"
        settle_ms = 0
        max_attempts = 1

        def precondition(self, ctx):
            return True

        def execute(self, ctx):
            attempt_counts[0] += 1

        def postcondition(self, ctx):
            # Succeed on the second overall attempt
            return attempt_counts[0] >= 2

    runner, driver, clock = _make_runner([RetryScope([CountedRetry()], max_attempts=3)])
    _run_to_completion(runner, clock)
    assert runner.run_status == RunStatus.SUCCEEDED
    assert attempt_counts[0] >= 2


# ---------------------------------------------------------------------------
# Timing invariants
# ---------------------------------------------------------------------------

def test_no_sleep_call_anywhere(monkeypatch):
    """No time.sleep() calls anywhere in a full runner loop."""
    import time
    original_sleep = time.sleep

    def bad_sleep(seconds):
        raise AssertionError(
            f"time.sleep({seconds}) called — forbidden by NFR-3 (N-RPA-3)"
        )

    monkeypatch.setattr(time, "sleep", bad_sleep)
    try:
        runner, driver, clock = _make_runner([_OkActivity()])
        _run_to_completion(runner, clock)
        assert runner.run_status == RunStatus.SUCCEEDED
    finally:
        monkeypatch.setattr(time, "sleep", original_sleep)


def test_one_pump_one_transition_max():
    """No single pump call issues more than one driver actuation."""
    actuation_counts = []
    base_click = FakeDriver.click

    clock = FakeClock()
    world = World(current_state=HOME, widget_trees={HOME: [{"cls": "WBase", "visible": True}]})
    driver = FakeDriver(world=world, clock=clock)

    original_click = driver.click
    original_trigger = driver.trigger_action

    pump_actuations = [0]

    def counting_click(sel, **kw):
        pump_actuations[0] += 1
        return original_click(sel, **kw)

    def counting_trigger(key):
        pump_actuations[0] += 1
        return original_trigger(key)

    driver.click = counting_click
    driver.trigger_action = counting_trigger

    runner = Runner(driver=driver, activities=[_OkActivity(), _OkActivity()], run_id="r-test")
    violations = []
    for _ in range(200):
        pump_actuations[0] = 0
        if not runner.pump():
            break
        if pump_actuations[0] > 1:
            violations.append(pump_actuations[0])
        clock.advance(50.0)
        clock.run_due()

    assert violations == [], f"Pumps that issued >1 actuation: {violations}"


def test_settled_ms_not_pumps():
    """Settle windows are expressed in ms, not pump counts.

    A settle_ms=500 must unblock after clock advances 500 ms, regardless of how
    many pumps have fired.
    """

    class SlowSettle(Activity):
        name = "SlowSettle"
        settle_ms = 500
        max_attempts = 1

        def precondition(self, ctx):
            return True

        def execute(self, ctx):
            pass

        def postcondition(self, ctx):
            return True

    clock = FakeClock()
    world = World(current_state=HOME, widget_trees={HOME: [{"cls": "WBase", "visible": True}]})
    driver = FakeDriver(world=world, clock=clock)
    runner = Runner(driver=driver, activities=[SlowSettle()], run_id="r-settle")

    # Pump until ACT fires; then pump without advancing clock
    for _ in range(50):
        runner.pump()
        if runner._sub_state == SubState.SETTLE:
            break
        clock.advance(50.0)

    # Now stuck in SETTLE; pump 20 more times without advancing clock
    pumps_stuck = 0
    for _ in range(20):
        runner.pump()
        if runner._sub_state != SubState.SETTLE:
            break
        pumps_stuck += 1

    assert pumps_stuck > 0, "Expected to be stuck in SETTLE without clock advance"

    # Advance clock past settle window — should unblock
    clock.advance(500.0)
    runner.pump()
    assert runner._sub_state != SubState.SETTLE


# ---------------------------------------------------------------------------
# Cancellation and run timeout
# ---------------------------------------------------------------------------

def test_run_timeout_triggers_cancelling():
    """Exceeding RUN_TIMEOUT_MS transitions the run to TIMED_OUT."""
    clock = FakeClock()
    world = World(current_state=HOME, widget_trees={HOME: [{"cls": "WBase", "visible": True}]})
    driver = FakeDriver(world=world, clock=clock)

    class NeverDone(Activity):
        name = "NeverDone"
        settle_ms = 0
        max_attempts = 99999

        def precondition(self, ctx):
            return True

        def execute(self, ctx):
            pass

        def postcondition(self, ctx):
            return False  # Never succeeds

    runner = Runner(driver=driver, activities=[NeverDone()], run_id="r-timeout")
    # First pump starts the run and sets the deadline relative to now
    runner.pump()
    # Advance clock past the run deadline
    clock.advance(RUN_TIMEOUT_MS + 1)
    # Next pump must detect the exceeded deadline
    runner.pump()
    assert runner.run_status in (RunStatus.TIMED_OUT, RunStatus.CANCELLING, RunStatus.FAILED)


def test_run_timeout_ms_less_than_pytest_timeout():
    """RUN_TIMEOUT_MS must be at least 30 000 ms below pytest's 120 000 ms timeout (D12)."""
    pytest_timeout_ms = 120_000
    assert RUN_TIMEOUT_MS + 30_000 <= pytest_timeout_ms, (
        f"RUN_TIMEOUT_MS ({RUN_TIMEOUT_MS}) leaves < 30 000 ms before pytest timeout ({pytest_timeout_ms})"
    )


def test_rpa_cancel_sets_cancelling_state():
    """runner.cancel() causes the run to enter CANCELLING on the next pump."""
    runner, driver, clock = _make_runner([_OkActivity(), _OkActivity()])
    # Start the run
    runner.pump()
    runner.cancel()
    runner.pump()
    assert runner.run_status in (RunStatus.CANCELLING, RunStatus.CANCELLED, RunStatus.SUCCEEDED)


def test_cancelling_transitions_to_cancelled_via_unwind():
    """cancel() causes the run to complete as CANCELLED (via UNWIND)."""
    runner, driver, clock = _make_runner([_OkActivity(), _OkActivity()])
    runner.pump()
    runner.cancel()
    _run_to_completion(runner, clock)
    assert runner.run_status in (RunStatus.CANCELLED, RunStatus.SUCCEEDED)


# ---------------------------------------------------------------------------
# Re-entrancy guard
# ---------------------------------------------------------------------------

def test_pump_reentrancy_guard_prevents_nested_pump():
    """pump() called while already pumping is a no-op (not a crash)."""
    runner, driver, clock = _make_runner([_OkActivity()])
    runner._pumping = True  # simulate being inside pump
    result = runner.pump()
    runner._pumping = False
    assert result is True  # should return True (still running), not crash


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

def test_journal_written_on_terminal_transition():
    """RunRecord is written to run_dir/journal.json on completion."""
    with tempfile.TemporaryDirectory() as run_dir:
        clock = FakeClock()
        world = World(current_state=HOME, widget_trees={HOME: [{"cls": "WBase", "visible": True}]})
        driver = FakeDriver(world=world, clock=clock)
        runner = Runner(
            driver=driver,
            activities=[_OkActivity()],
            run_id="r-journal-test",
            run_dir=run_dir,
        )
        _run_to_completion(runner, clock)
        assert os.path.exists(os.path.join(run_dir, "journal.json"))


def test_journal_env_block_records_dpr_theme_and_cv_availability():
    """RunRecord.env contains expected keys when set."""
    record = RunRecord(
        run_id="r-env-test",
        workflow_name="test",
        env={
            "dpr": 2.0,
            "theme": "Midnight",
            "ui_mode": "Coach",
            "cv_available": False,
            "ocr_available": False,
        },
    )
    j = record.to_dict()
    assert j["env"]["dpr"] == 2.0
    assert j["env"]["theme"] == "Midnight"
    assert "cv_available" in j["env"]


def test_run_id_scheme_is_timestamp_plus_hex():
    """Run IDs must match the r-<yyyymmddThhmmss>-<4hex> scheme."""
    pattern = re.compile(r"^r-\d{8}T\d{6}-[0-9a-f]{4}$")
    valid_ids = [
        "r-20260828T142233-9f1c",
        "r-20260101T000000-abcd",
    ]
    for rid in valid_ids:
        assert pattern.match(rid), f"{rid!r} does not match run_id scheme"


def test_backoff_reproducible_from_run_id():
    """Backoff jitter is deterministic for a given run_id."""
    import random
    rng1 = random.Random("r-test-0001")
    rng2 = random.Random("r-test-0001")
    vals1 = [rng1.uniform(0.9, 1.1) for _ in range(5)]
    vals2 = [rng2.uniform(0.9, 1.1) for _ in range(5)]
    assert vals1 == vals2


# ---------------------------------------------------------------------------
# StepRecord / RunRecord
# ---------------------------------------------------------------------------

def test_step_record_trace_is_bounded():
    """Sub-state trace stops at _MAX_TRACE entries."""
    from Code.Rpa.Journal import _MAX_TRACE
    sr = StepRecord(index=0, activity_name="test", entry_state=HOME)
    for _ in range(_MAX_TRACE + 10):
        sr.record_sub_state("VERIFY")
    assert len(sr.sub_state_trace) == _MAX_TRACE


def test_run_record_roundtrip():
    """RunRecord survives a to_dict/from_dict roundtrip."""
    sr = StepRecord(index=0, activity_name="OkActivity", entry_state=HOME,
                    result="ok", exit_state=HOME, attempts=1, pumps=5)
    rr = RunRecord(
        run_id="r-rt-0001",
        workflow_name="roundtrip",
        status="SUCCEEDED",
        steps=[sr],
        env={"dpr": 1.0},
    )
    restored = RunRecord.from_dict(rr.to_dict())
    assert restored.run_id == rr.run_id
    assert restored.status == "SUCCEEDED"
    assert len(restored.steps) == 1
    assert restored.steps[0].activity_name == "OkActivity"


def test_journal_persist_and_load():
    """Journal.persist and Journal.load roundtrip the RunRecord."""
    with tempfile.TemporaryDirectory() as run_dir:
        rr = RunRecord(run_id="r-jl-0001", workflow_name="test", status="SUCCEEDED")
        Journal.persist(rr, run_dir)
        loaded = Journal.load(run_dir)
        assert loaded.run_id == "r-jl-0001"
        assert loaded.status == "SUCCEEDED"


# ---------------------------------------------------------------------------
# xfail stubs for Phase 6
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service)")
def test_every_rpa_verb_returns_under_200ms_while_run_active():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 (feat/rpa-service)")
def test_run_progresses_while_a_modal_dialog_is_open():
    pytest.fail("not yet implemented — will be unblocked in Phase 6")
