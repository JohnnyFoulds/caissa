"""
bin/Code/Rpa/Activities.py — Activity base class and UiPath-named concrete activities.

An **Activity** is a single unit of automation work.  The runner executes activities
in the closed 5-step loop: CHECK_PRE → (CONVERGE →) ACT → SETTLE → VERIFY → STEP_EXIT.

Each activity declares:

- :attr:`required_state` — which app state the precondition requires.  The runner
  calls ``StateGraph.plan`` to converge to this state before ``precondition`` is checked.
- :attr:`settle_ms` — milliseconds to wait after ``execute`` before the first VERIFY.
- :attr:`max_attempts` — how many ``CHECK_PRE → ACT → VERIFY`` cycles to allow.
- :attr:`compensable` — whether ``compensate`` does anything useful.

:spec: FR-2, §5 (feature_spec.md)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Code.Rpa.Types import Snapshot

logger = logging.getLogger(__name__)


class Context:
    """Shared state passed to every activity method during a run.

    :param driver: The driver instance (``QtDriver`` in production, ``FakeDriver`` in tests).
    :param graph: ``StateGraph`` for convergence planning.
    :param run_id: Run identifier (used for deterministic backoff jitter).
    :param extra: Caller-supplied extras (e.g. workflow params).
    """

    def __init__(
        self,
        driver,
        graph,
        run_id: str,
        extra: dict | None = None,
        run_dir: str | None = None,
    ) -> None:
        """Initialise the context.

        :param driver: Driver instance.
        :param graph: StateGraph instance.
        :param run_id: Run identifier string.
        :param extra: Optional dict of caller-supplied workflow parameters.
        :param run_dir: Journal output directory; ``None`` skips persistence.
        """
        self.driver = driver
        self.graph = graph
        self.run_id: str = run_id
        self.run_dir: str | None = run_dir
        self.extra: dict = extra or {}
        self.snapshot: "Snapshot | None" = None  # refreshed at CHECK_PRE

    def refresh_snapshot(self) -> "Snapshot":
        """Refresh and return the current snapshot.

        :returns: The new snapshot, also stored as ``self.snapshot``.
        """
        self.snapshot = self.driver.snapshot()
        return self.snapshot


class Activity:
    """Base class for all RPA activities.

    Subclasses must override :meth:`precondition`, :meth:`execute`, and
    :meth:`postcondition`.  :meth:`compensate` only needs overriding when
    :attr:`compensable` is ``True``.

    :cvar name: Human-readable activity name (used in journal records).
    :cvar settle_ms: Milliseconds to wait after :meth:`execute` before VERIFY.
    :cvar max_attempts: Maximum number of CHECK_PRE → ACT → VERIFY cycles.
    :cvar compensable: Whether :meth:`compensate` provides a useful undo.
    :cvar required_state: App state required before :meth:`precondition` is tested;
        ``None`` means any state is accepted.
    """

    name: str = "Activity"
    settle_ms: int = 200
    max_attempts: int = 1
    compensable: bool = False
    required_state: str | None = None

    def precondition(self, ctx: Context) -> bool:
        """Return True if the app is in the right state to execute this activity.

        :param ctx: Current run context.
        :returns: True if the activity may proceed.
        :raises NotImplementedError: Subclasses must override this.
        """
        raise NotImplementedError(f"{type(self).__name__}.precondition not implemented")

    def execute(self, ctx: Context) -> None:
        """Perform the UI action.

        Must be fast and non-blocking.  Use ``ctx.driver.defer()`` for delayed work.

        :param ctx: Current run context.
        :raises NotImplementedError: Subclasses must override this.
        """
        raise NotImplementedError(f"{type(self).__name__}.execute not implemented")

    def postcondition(self, ctx: Context) -> bool:
        """Return True if the action was performed successfully.

        Called once per pump during VERIFY.  Must be fast and non-blocking.

        :param ctx: Current run context.
        :returns: True if the postcondition is satisfied.
        :raises NotImplementedError: Subclasses must override this.
        """
        raise NotImplementedError(f"{type(self).__name__}.postcondition not implemented")

    def compensate(self, ctx: Context) -> None:
        """Undo the effect of :meth:`execute`.

        Only called when :attr:`compensable` is ``True``.

        :param ctx: Current run context.
        :raises NotImplementedError: Default implementation; override when compensable=True.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.compensate not implemented "
            f"(set compensable=True and override this method)"
        )

    def prepare_next(self, ctx: Context) -> None:
        """Called at STEP_EXIT to prepare for the next activity.

        Default is a no-op.  Override to update context state between activities.

        :param ctx: Current run context.
        """


# ---------------------------------------------------------------------------
# UiPath-named concrete activities
# ---------------------------------------------------------------------------

class Click(Activity):
    """Click a UI element identified by a selector string.

    :param selector: Widget selector (compact string or JSON).
    :param settle_ms: Time to wait after the click before verifying.
    """

    name: str = "Click"
    settle_ms: int = 200
    max_attempts: int = 3
    compensable: bool = False

    def __init__(self, selector: str, settle_ms: int = 200) -> None:
        """Initialise Click.

        :param selector: Widget selector.
        :param settle_ms: Settle time in milliseconds.
        """
        self.selector = selector
        self.settle_ms = settle_ms

    def precondition(self, ctx: Context) -> bool:
        """True if the target element is visible.

        :param ctx: Current run context.
        :returns: True if element is found in the snapshot.
        """
        if ctx.snapshot is None:
            return False
        return any(
            w.get("object_name") == self.selector or self.selector in (w.get("text") or "")
            for w in ctx.snapshot.widget_tree
            if w.get("visible", True)
        )

    def execute(self, ctx: Context) -> None:
        """Click the target element.

        :param ctx: Current run context.
        """
        ctx.driver.click(self.selector)

    def postcondition(self, ctx: Context) -> bool:
        """True unconditionally — click has no verifiable post-state.

        :param ctx: Current run context.
        :returns: Always True.
        """
        return True


class TypeInto(Activity):
    """Type text into a widget identified by a selector.

    :param selector: Widget selector.
    :param value: Text to type.
    """

    name: str = "TypeInto"
    settle_ms: int = 100
    max_attempts: int = 2

    def __init__(self, selector: str, value: str) -> None:
        """Initialise TypeInto.

        :param selector: Widget selector.
        :param value: Text to enter.
        """
        self.selector = selector
        self.value = value

    def precondition(self, ctx: Context) -> bool:
        """True if the target field is visible.

        :param ctx: Current run context.
        :returns: True if field is found in snapshot.
        """
        if ctx.snapshot is None:
            return False
        return any(
            w.get("object_name") == self.selector
            for w in ctx.snapshot.widget_tree
            if w.get("visible", True)
        )

    def execute(self, ctx: Context) -> None:
        """Set text on the target field.

        :param ctx: Current run context.
        """
        ctx.driver.set_text(self.selector, self.value)

    def postcondition(self, ctx: Context) -> bool:
        """True unconditionally.

        :param ctx: Current run context.
        :returns: Always True.
        """
        return True


class SelectItem(Activity):
    """Select an item in a QComboBox.

    :param selector: Widget selector.
    :param value: Item text to select.
    """

    name: str = "SelectItem"
    settle_ms: int = 100
    max_attempts: int = 2

    def __init__(self, selector: str, value: str) -> None:
        """Initialise SelectItem.

        :param selector: Widget selector.
        :param value: Combo item text.
        """
        self.selector = selector
        self.value = value

    def precondition(self, ctx: Context) -> bool:
        """True if the combo widget is visible.

        :param ctx: Current run context.
        :returns: True if found in snapshot.
        """
        if ctx.snapshot is None:
            return False
        return any(
            w.get("object_name") == self.selector
            for w in ctx.snapshot.widget_tree
            if w.get("visible", True)
        )

    def execute(self, ctx: Context) -> None:
        """Select the item.

        :param ctx: Current run context.
        """
        ctx.driver.select_combo(self.selector, self.value)

    def postcondition(self, ctx: Context) -> bool:
        """True unconditionally.

        :param ctx: Current run context.
        :returns: Always True.
        """
        return True


class GetText(Activity):
    """Read text from a UI element and store it in ``ctx.extra``.

    :param selector: Widget selector.
    :param key: Key under which to store the result in ``ctx.extra``.
    """

    name: str = "GetText"
    settle_ms: int = 0
    max_attempts: int = 1

    def __init__(self, selector: str, key: str = "text") -> None:
        """Initialise GetText.

        :param selector: Widget selector.
        :param key: Storage key in ``ctx.extra``.
        """
        self.selector = selector
        self.key = key

    def precondition(self, ctx: Context) -> bool:
        """True if the widget is visible.

        :param ctx: Current run context.
        :returns: True if found.
        """
        if ctx.snapshot is None:
            return False
        return any(
            w.get("object_name") == self.selector
            for w in ctx.snapshot.widget_tree
            if w.get("visible", True)
        )

    def execute(self, ctx: Context) -> None:
        """Read text and store it.

        :param ctx: Current run context.
        """
        if ctx.snapshot:
            for w in ctx.snapshot.widget_tree:
                if w.get("object_name") == self.selector:
                    ctx.extra[self.key] = w.get("text", "")
                    break

    def postcondition(self, ctx: Context) -> bool:
        """True if the key was set in ctx.extra.

        :param ctx: Current run context.
        :returns: True if key is present.
        """
        return self.key in ctx.extra


class ElementExists(Activity):
    """Assert that an element exists; fail fast if not.

    :param selector: Widget selector.
    :param expected: If True, the element must exist; if False, must be absent.
    """

    name: str = "ElementExists"
    settle_ms: int = 0
    max_attempts: int = 1

    def __init__(self, selector: str, expected: bool = True) -> None:
        """Initialise ElementExists.

        :param selector: Widget selector.
        :param expected: Expected presence (True = must exist, False = must be absent).
        """
        self.selector = selector
        self.expected = expected
        self._found: bool = False

    def precondition(self, ctx: Context) -> bool:
        """Always True — this activity checks existence as its postcondition.

        :param ctx: Current run context.
        :returns: Always True.
        """
        return True

    def execute(self, ctx: Context) -> None:
        """Check and record element presence.

        :param ctx: Current run context.
        """
        if ctx.snapshot is None:
            self._found = False
            return
        self._found = any(
            w.get("object_name") == self.selector or self.selector in (w.get("text") or "")
            for w in ctx.snapshot.widget_tree
            if w.get("visible", True)
        )

    def postcondition(self, ctx: Context) -> bool:
        """True if presence matches expectation.

        :param ctx: Current run context.
        :returns: True if ``self._found == self.expected``.
        """
        return self._found == self.expected


class TakeScreenshot(Activity):
    """Capture a screenshot and store the path in ctx.extra.

    :param path: Output file path.
    :param key: Key under which to store the path in ``ctx.extra``.
    """

    name: str = "TakeScreenshot"
    settle_ms: int = 0
    max_attempts: int = 1

    def __init__(self, path: str, key: str = "screenshot") -> None:
        """Initialise TakeScreenshot.

        :param path: Output path for the screenshot PNG.
        :param key: Storage key in ``ctx.extra``.
        """
        self.path = path
        self.key = key

    def precondition(self, ctx: Context) -> bool:
        """Always True.

        :param ctx: Current run context.
        :returns: True.
        """
        return True

    def execute(self, ctx: Context) -> None:
        """Capture the screenshot.

        :param ctx: Current run context.
        """
        ctx.extra[self.key] = ctx.driver.capture(self.path)

    def postcondition(self, ctx: Context) -> bool:
        """True if the path was stored.

        :param ctx: Current run context.
        :returns: True if key is present.
        """
        return self.key in ctx.extra


class OpenConfig(Activity):
    """Open the General Configuration dialog.

    :cvar required_state: Requires HOME state (dialog must not already be open).
    """

    name: str = "OpenConfig"
    settle_ms: int = 300
    max_attempts: int = 2
    compensable: bool = True
    required_state: str = "HOME"

    def precondition(self, ctx: Context) -> bool:
        """True if at HOME (no config dialog currently open).

        :param ctx: Current run context.
        :returns: True when at HOME.
        """
        if ctx.snapshot is None:
            return False
        from Code.Rpa.AppState import recognise, HOME
        return recognise(ctx.snapshot) == HOME

    def execute(self, ctx: Context) -> None:
        """Trigger the Options action to open config.

        :param ctx: Current run context.
        """
        ctx.driver.trigger_action("Options")

    def postcondition(self, ctx: Context) -> bool:
        """True if the config dialog is now visible.

        :param ctx: Current run context.
        :returns: True when DIALOG_CONFIG is recognised.
        """
        snap = ctx.refresh_snapshot()
        from Code.Rpa.AppState import recognise, DIALOG_CONFIG
        return recognise(snap) == DIALOG_CONFIG

    def compensate(self, ctx: Context) -> None:
        """Close the config dialog if it was opened.

        :param ctx: Current run context.
        """
        ctx.driver.trigger_action("Cancel")


class CloseDialog(Activity):
    """Close the topmost modal dialog by clicking Cancel/close.

    :cvar required_state: Requires ``DIALOG_OTHER`` or ``DIALOG_CONFIG``.
    """

    name: str = "CloseDialog"
    settle_ms: int = 150
    max_attempts: int = 2

    def precondition(self, ctx: Context) -> bool:
        """True if a dialog is visible.

        :param ctx: Current run context.
        :returns: True if DIALOG_CONFIG or DIALOG_OTHER is active.
        """
        if ctx.snapshot is None:
            return False
        from Code.Rpa.AppState import recognise, DIALOG_CONFIG, DIALOG_OTHER
        state = recognise(ctx.snapshot)
        return state in (DIALOG_CONFIG, DIALOG_OTHER)

    def execute(self, ctx: Context) -> None:
        """Trigger Cancel to close the dialog.

        :param ctx: Current run context.
        """
        ctx.driver.trigger_action("Cancel")

    def postcondition(self, ctx: Context) -> bool:
        """True if no dialog is visible.

        :param ctx: Current run context.
        :returns: True if state is no longer a dialog state.
        """
        snap = ctx.refresh_snapshot()
        from Code.Rpa.AppState import recognise, DIALOG_CONFIG, DIALOG_OTHER
        state = recognise(snap)
        return state not in (DIALOG_CONFIG, DIALOG_OTHER)


class SwitchTab(Activity):
    """Click a tab in a QTabWidget.

    :param tab_text: Label of the tab to switch to.
    """

    name: str = "SwitchTab"
    settle_ms: int = 100
    max_attempts: int = 2

    def __init__(self, tab_text: str) -> None:
        """Initialise SwitchTab.

        :param tab_text: Tab label text.
        """
        self.tab_text = tab_text

    def precondition(self, ctx: Context) -> bool:
        """Always True — we attempt the click and verify the result.

        :param ctx: Current run context.
        :returns: True.
        """
        return True

    def execute(self, ctx: Context) -> None:
        """Trigger the tab-click action.

        :param ctx: Current run context.
        """
        ctx.driver.trigger_action(f"tab:{self.tab_text}")

    def postcondition(self, ctx: Context) -> bool:
        """Always True — tab state is not easily verifiable without widget inspection.

        :param ctx: Current run context.
        :returns: Always True.
        """
        return True


class Sequence(Activity):
    """Execute a list of activities in order.

    :class:`Sequence` is handled specially by the runner: it pushes a ``SequenceFrame``
    onto the frame stack and the runner processes its activities one at a time.

    :param activities: Ordered list of activities to execute.
    """

    name: str = "Sequence"
    settle_ms: int = 0
    max_attempts: int = 1

    def __init__(self, activities: list[Activity]) -> None:
        """Initialise Sequence.

        :param activities: Sub-activities to run in order.
        """
        self.activities = list(activities)

    def precondition(self, ctx: Context) -> bool:
        """Always True — frame push is unconditional.

        :param ctx: Current run context.
        :returns: True.
        """
        return True

    def execute(self, ctx: Context) -> None:
        """No-op — the runner sees Sequence and pushes a frame instead.

        :param ctx: Current run context.
        """

    def postcondition(self, ctx: Context) -> bool:
        """Always True — frame completion is tracked by the runner.

        :param ctx: Current run context.
        :returns: True.
        """
        return True


class RetryScope(Activity):
    """Execute a list of activities with automatic retry on failure.

    :class:`RetryScope` is handled specially by the runner: it pushes a
    ``RetryScopeFrame`` onto the frame stack.

    :param activities: Ordered list of activities to retry as a unit.
    :param max_attempts: Maximum number of attempts before the scope fails.
    """

    name: str = "RetryScope"
    settle_ms: int = 0

    def __init__(self, activities: list[Activity], max_attempts: int = 3) -> None:
        """Initialise RetryScope.

        :param activities: Sub-activities that are retried as a unit.
        :param max_attempts: Maximum number of attempts.
        """
        self.activities = list(activities)
        self.max_attempts = max_attempts

    def precondition(self, ctx: Context) -> bool:
        """Always True — frame push is unconditional.

        :param ctx: Current run context.
        :returns: True.
        """
        return True

    def execute(self, ctx: Context) -> None:
        """No-op — the runner sees RetryScope and pushes a frame instead.

        :param ctx: Current run context.
        """

    def postcondition(self, ctx: Context) -> bool:
        """Always True — frame completion is tracked by the runner.

        :param ctx: Current run context.
        :returns: True.
        """
        return True
