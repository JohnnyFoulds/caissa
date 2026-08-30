"""
FakeDriver, FakeClock, and World — the testability keystone.

These classes ship in production (not just in tests) so that
``tools/caissa-rpa capture-world`` can generate ``Resources/Rpa/Fixtures/world.json``
and ``dry_run=True`` can validate workflow selector syntax and state-graph
reachability without a running Qt application.  (Decision D1.)

No PySide6 import anywhere in this module (N-RPA-2).

Usage in unit tests::

    clock = FakeClock(start_ms=0.0)
    world = World(
        current_state="HOME",
        widget_trees={"HOME": [{"cls": "QPushButton", "text": "Play"}]},
    )
    driver = FakeDriver(world=world, clock=clock)
    snap = driver.snapshot()
    assert snap.state_name == "HOME"
    clock.advance(500.0)
    clock.run_due()
"""

from __future__ import annotations

import dataclasses
import logging
import typing

from Code.Rpa.Driver import Driver
from Code.Rpa.Types import Snapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FakeClock
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class _Pending:
    """A scheduled callback waiting to fire at ``fire_at_ms``."""
    fire_at_ms: float
    callback: typing.Callable[[], None]


class FakeClock:
    """Deterministic clock for unit-testing the RPA engine.

    All deadlines, settle windows, and backoff calculations in
    :class:`~Code.Rpa.Runner.Runner` are expressed in ``driver.now()`` terms;
    by controlling this clock tests can exercise the entire timing machinery
    at zero wall-clock cost.

    :param start_ms: Initial ``now_ms`` value (default 0.0).
    """

    def __init__(self, start_ms: float = 0.0) -> None:
        """Initialise the fake clock.

        :param start_ms: Initial ``now_ms`` value (default 0.0).
        """
        self.now_ms: float = start_ms
        self._pending: list[_Pending] = []

    def advance(self, ms: float) -> None:
        """Advance the clock by ``ms`` milliseconds without firing callbacks.

        Call :meth:`run_due` after advancing to fire any callbacks whose
        deadline has passed.

        :param ms: Milliseconds to advance.
        """
        self.now_ms += ms

    def defer(self, ms: float, callback: typing.Callable[[], None]) -> None:
        """Schedule ``callback`` to fire at ``now_ms + ms``.

        :param ms:       Delay in milliseconds.
        :param callback: Zero-argument callable.
        """
        self._pending.append(_Pending(fire_at_ms=self.now_ms + ms, callback=callback))

    def run_due(self) -> int:
        """Fire all callbacks whose deadline is ``<= now_ms``.

        :returns: Number of callbacks fired.
        """
        due = [p for p in self._pending if p.fire_at_ms <= self.now_ms]
        self._pending = [p for p in self._pending if p.fire_at_ms > self.now_ms]
        for p in sorted(due, key=lambda x: x.fire_at_ms):
            try:
                p.callback()
            except Exception:
                logger.exception("FakeClock callback raised")
        return len(due)

    def pending_count(self) -> int:
        """Return the number of not-yet-fired scheduled callbacks.

        :returns: Pending callback count.
        """
        return len(self._pending)


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class World:
    """A description of a fake application state used by :class:`FakeDriver`.

    :param current_state:   The name of the current app state (e.g. ``"HOME"``).
    :param widget_trees:    Mapping of state name → list of widget-info dicts.
                            :meth:`FakeDriver.snapshot` returns the tree for
                            ``current_state``.
    :param transition_effects: Optional mapping of transition name →
                                resulting state name.  Used by future phases to
                                simulate state transitions without a real Qt app.
    """
    current_state: str
    widget_trees: dict[str, list[dict]] = dataclasses.field(default_factory=dict)
    transition_effects: dict[str, str] = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# FakeDriver
# ---------------------------------------------------------------------------

class FakeDriver(Driver):
    """Test-double driver backed by a :class:`World` fixture and a :class:`FakeClock`.

    Implements all eight :class:`~Code.Rpa.Driver.Driver` abstract methods.
    UI-mutating methods (:meth:`click`, :meth:`set_text`, etc.) record their
    calls for assertion in tests but do not modify the world — extend this
    class if you need side-effect simulation in integration tests.

    :param world: Application state fixture.
    :param clock: Deterministic clock; a default :class:`FakeClock` is created
                  at ``now_ms=0.0`` if not provided.
    """

    def __init__(self, world: World | None = None, clock: FakeClock | None = None) -> None:
        """Initialise the fake driver.

        :param world: World fixture describing the simulated UI state.
            Defaults to a minimal HOME world.
        :param clock: Deterministic clock.  Defaults to a fresh
            :class:`FakeClock` at ``now_ms=0.0``.
        """
        self.world: World = world or World(current_state="HOME")
        self.clock: FakeClock = clock or FakeClock()
        self.calls: list[dict] = []  # recorded actuation calls for assertion

    # ------------------------------------------------------------------
    # Driver interface
    # ------------------------------------------------------------------

    def snapshot(self, depth: int = 3) -> Snapshot:
        """Return a Snapshot built from the current world state.

        :param depth: Ignored — the world fixture is flat.
        :returns:     :class:`~Code.Rpa.Types.Snapshot` for ``world.current_state``.
        """
        tree = self.world.widget_trees.get(self.world.current_state, [])
        return Snapshot(
            state_name=self.world.current_state,
            widget_tree=tree,
            timestamp_ms=self.clock.now_ms,
        )

    def click(self, selector: str, target_type: str = "widget") -> dict:
        """Record a click call and return ok.

        :param selector:    Widget selector string.
        :param target_type: ``"widget"`` (default) or ``"toolbar"``.
        :returns:           ``{"ok": True, "selector": selector}``.
        """
        self.calls.append({"method": "click", "selector": selector, "target_type": target_type})
        return {"ok": True, "selector": selector}

    def set_text(self, selector: str, value: str) -> dict:
        """Record a set_text call and return ok.

        :param selector: Widget selector string.
        :param value:    New text value.
        :returns:        ``{"ok": True, "value": value}``.
        """
        self.calls.append({"method": "set_text", "selector": selector, "value": value})
        return {"ok": True, "value": value}

    def select_combo(self, selector: str, value: str) -> dict:
        """Record a select_combo call and return ok.

        :param selector: Widget selector string.
        :param value:    Item text.
        :returns:        ``{"ok": True, "selected": value}``.
        """
        self.calls.append({"method": "select_combo", "selector": selector, "value": value})
        return {"ok": True, "selected": value}

    def trigger_action(self, key: str) -> dict:
        """Record a trigger_action call and return ok.

        :param key: Action key.
        :returns:   ``{"ok": True, "key": key}``.
        """
        self.calls.append({"method": "trigger_action", "key": key})
        return {"ok": True, "key": key}

    def now(self) -> float:
        """Return the current fake clock time in milliseconds.

        :returns: ``clock.now_ms``.
        """
        return self.clock.now_ms

    def defer(self, ms: float, callback: typing.Callable[[], None]) -> None:
        """Schedule ``callback`` on the fake clock.

        :param ms:       Delay in milliseconds.
        :param callback: Zero-argument callable.
        """
        self.clock.defer(ms, callback)

    def capture(self, path: str) -> str:
        """Record a capture call; returns the path without writing a file.

        :param path: Output path (not actually written).
        :returns:    ``path`` unchanged.
        """
        self.calls.append({"method": "capture", "path": path})
        return path
