"""
Phase 2-B — Driver seam unit tests.

Tests for :class:`~Code.Rpa.Driver.Driver` (base class contract),
:class:`~Code.Rpa.Fakes.FakeDriver`, and :class:`~Code.Rpa.Fakes.FakeClock`.
All tests run without Qt (no PySide6 import required).

:class:`~Code.Rpa.Driver.QtDriver` is **not** tested here — it requires a live
QApplication and is covered by the ``rpa_ui`` suite instead.  The contract test
``test_qt_driver_overrides_all_driver_methods`` verifies structural completeness
by inspecting the class without instantiating it.
"""

import inspect

import pytest

pytestmark = pytest.mark.rpa

from Code.Rpa.Driver import Driver, QtDriver
from Code.Rpa.Fakes import FakeClock, FakeDriver, World
from Code.Rpa.Types import Snapshot


# ---------------------------------------------------------------------------
# Driver base contract
# ---------------------------------------------------------------------------

def test_driver_base_raises_not_implemented_for_all_methods():
    """Every Driver method raises NotImplementedError when called on the base class."""
    d = Driver()
    for method_name in ("snapshot", "click", "set_text", "select_combo",
                        "trigger_action", "now", "defer", "capture"):
        method = getattr(d, method_name)
        with pytest.raises(NotImplementedError):
            # Supply minimal valid arguments for each signature
            if method_name == "snapshot":
                method()
            elif method_name == "click":
                method("selector")
            elif method_name in ("set_text", "select_combo"):
                method("selector", "value")
            elif method_name == "trigger_action":
                method("key")
            elif method_name == "now":
                method()
            elif method_name == "defer":
                method(0, lambda: None)
            elif method_name == "capture":
                method("/tmp/test.png")


def _driver_abstract_methods() -> set[str]:
    """Return the set of abstract method names declared on Driver."""
    return {
        name for name, _ in inspect.getmembers(Driver, predicate=inspect.isfunction)
        if not name.startswith("_")
    }


def test_fake_driver_overrides_all_driver_methods():
    """FakeDriver must override every method declared on Driver."""
    base_methods = _driver_abstract_methods()
    for method_name in base_methods:
        assert method_name in FakeDriver.__dict__ or any(
            method_name in cls.__dict__ for cls in FakeDriver.__mro__[1:]
            if cls is not Driver and cls is not object
        ), f"FakeDriver does not override Driver.{method_name}"


def test_qt_driver_overrides_all_driver_methods():
    """QtDriver must override every method declared on Driver (structural check only)."""
    base_methods = _driver_abstract_methods()
    for method_name in base_methods:
        assert method_name in QtDriver.__dict__ or any(
            method_name in cls.__dict__ for cls in QtDriver.__mro__[1:]
            if cls is not Driver and cls is not object
        ), f"QtDriver does not override Driver.{method_name}"


# ---------------------------------------------------------------------------
# FakeClock
# ---------------------------------------------------------------------------

def test_fake_clock_starts_at_given_time():
    """FakeClock.now_ms is the value passed to start_ms."""
    clock = FakeClock(start_ms=1000.0)
    assert clock.now_ms == 1000.0


def test_fake_clock_advance_updates_now():
    """FakeClock.advance(ms) increments now_ms by ms."""
    clock = FakeClock(start_ms=0.0)
    clock.advance(250.0)
    assert clock.now_ms == 250.0
    clock.advance(100.0)
    assert clock.now_ms == 350.0


def test_fake_clock_run_due_fires_scheduled_callbacks():
    """FakeClock.run_due() fires callbacks whose fire_at_ms <= now_ms."""
    clock = FakeClock(start_ms=0.0)
    fired = []
    clock.defer(100.0, lambda: fired.append("a"))
    clock.defer(200.0, lambda: fired.append("b"))

    clock.advance(100.0)
    count = clock.run_due()
    assert count == 1
    assert fired == ["a"]

    clock.advance(100.0)
    count = clock.run_due()
    assert count == 1
    assert fired == ["a", "b"]


def test_fake_clock_run_due_fires_in_deadline_order():
    """Callbacks are fired in fire_at_ms order, not registration order."""
    clock = FakeClock(start_ms=0.0)
    fired = []
    clock.defer(200.0, lambda: fired.append("later"))
    clock.defer(100.0, lambda: fired.append("sooner"))
    clock.advance(300.0)
    clock.run_due()
    assert fired == ["sooner", "later"]


def test_fake_clock_pending_count_decreases_after_run_due():
    """pending_count() reflects the number of not-yet-fired callbacks."""
    clock = FakeClock()
    clock.defer(10.0, lambda: None)
    clock.defer(20.0, lambda: None)
    assert clock.pending_count() == 2
    clock.advance(10.0)
    clock.run_due()
    assert clock.pending_count() == 1


# ---------------------------------------------------------------------------
# FakeDriver
# ---------------------------------------------------------------------------

def test_fake_driver_snapshot_returns_world_state():
    """FakeDriver.snapshot() returns a Snapshot for the world's current_state."""
    widgets = [{"class": "QPushButton", "text": "Play"}]
    world = World(
        current_state="HOME",
        widget_trees={"HOME": widgets},
    )
    clock = FakeClock(start_ms=500.0)
    driver = FakeDriver(world=world, clock=clock)

    snap = driver.snapshot()

    assert isinstance(snap, Snapshot)
    assert snap.state_name == "HOME"
    assert snap.widget_tree == widgets
    assert snap.timestamp_ms == 500.0


def test_fake_driver_snapshot_empty_tree_for_unknown_state():
    """FakeDriver.snapshot() returns an empty widget_tree for unmapped states."""
    world = World(current_state="UNKNOWN")
    driver = FakeDriver(world=world)
    snap = driver.snapshot()
    assert snap.widget_tree == []


def test_fake_driver_defer_schedules_via_fake_clock():
    """FakeDriver.defer() enqueues on its FakeClock."""
    clock = FakeClock()
    driver = FakeDriver(clock=clock)
    fired = []
    driver.defer(50.0, lambda: fired.append(True))
    assert clock.pending_count() == 1
    clock.advance(50.0)
    clock.run_due()
    assert fired == [True]


def test_fake_driver_now_returns_clock_time():
    """FakeDriver.now() returns FakeClock.now_ms."""
    clock = FakeClock(start_ms=1234.5)
    driver = FakeDriver(clock=clock)
    assert driver.now() == 1234.5


def test_fake_driver_records_click_calls():
    """FakeDriver.click() records the call for test assertions."""
    driver = FakeDriver()
    result = driver.click("MyButton", target_type="toolbar")
    assert result == {"ok": True, "selector": "MyButton"}
    assert driver.calls == [{"method": "click", "selector": "MyButton", "target_type": "toolbar"}]


def test_fake_driver_records_set_text_calls():
    """FakeDriver.set_text() records the call and returns ok."""
    driver = FakeDriver()
    result = driver.set_text("NameField", "Alice")
    assert result["ok"] is True
    assert driver.calls[-1]["method"] == "set_text"


def test_fake_driver_capture_returns_path_without_writing():
    """FakeDriver.capture() returns the path without creating a file."""
    import os
    driver = FakeDriver()
    path = "/tmp/fake_driver_test_capture.png"
    result = driver.capture(path)
    assert result == path
    assert not os.path.exists(path), "FakeDriver must not create the file"
