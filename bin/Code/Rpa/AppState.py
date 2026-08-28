"""
bin/Code/Rpa/AppState.py — App-state recogniser, transition registry, and Dijkstra planner.

The app can be in one of 8 mutually exclusive states.  The recogniser reads a
:class:`~Code.Rpa.Types.Snapshot` and returns the most specific matching state
using a **dialog-first** priority (a modal dialog always blocks background state).

:data:`TRANSITION_TABLE` is the single source of truth for how the runner navigates
between states.  :class:`StateGraph` wraps it with a Dijkstra planner.

:spec: FR-5, §7 (feature_spec.md); `docs/rpa/states.md`
"""

from __future__ import annotations

import dataclasses
import heapq
import logging
from typing import Any, Callable

from Code.Rpa.Errors import ConvergeError
from Code.Rpa.Types import Snapshot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

DIALOG_CONFIG: str = "DIALOG_CONFIG"
"""A ``WindowConfig`` dialog is visible and active — highest priority."""

DIALOG_OTHER: str = "DIALOG_OTHER"
"""Any other modal dialog is visible."""

GAME_OVER: str = "GAME_OVER"
"""Game manager visible; game is in a terminal state (checkmate, draw, resign)."""

ENGINE_THINKING: str = "ENGINE_THINKING"
"""Engine manager active; engine is calculating — no user actions possible."""

PLAYING: str = "PLAYING"
"""Engine manager active; waiting for the player's move."""

MANAGER_OTHER: str = "MANAGER_OTHER"
"""A non-engine manager is active (training, analysis, puzzles, etc.)."""

HOME: str = "HOME"
"""No active game or dialog; main window toolbar visible. Default convergence target."""

UNKNOWN: str = "UNKNOWN"
"""None of the above conditions matched. Always has a path to ``HOME``."""

ALL_STATES: frozenset[str] = frozenset({
    DIALOG_CONFIG, DIALOG_OTHER, GAME_OVER, ENGINE_THINKING,
    PLAYING, MANAGER_OTHER, HOME, UNKNOWN,
})

# Recognition priority — ordered list used by recognise()
_PRIORITY: list[str] = [
    DIALOG_CONFIG,
    DIALOG_OTHER,
    GAME_OVER,
    ENGINE_THINKING,
    PLAYING,
    MANAGER_OTHER,
    HOME,
    UNKNOWN,
]


# ---------------------------------------------------------------------------
# Recogniser
# ---------------------------------------------------------------------------

def _any_modal_dialog(widget_tree: list[dict[str, Any]]) -> bool:
    """Return True if any widget in the tree indicates a modal dialog is active.

    :param widget_tree: Widget info dicts from the snapshot.
    :returns: True if a modal dialog is detected.
    """
    for w in widget_tree:
        if w.get("modal"):
            return True
        cls = w.get("cls", "")
        if "Dialog" in cls or "WindowConfig" in cls:
            return True
    return False


def _is_config_dialog(widget_tree: list[dict[str, Any]]) -> bool:
    """Return True if the topmost dialog looks like the General Configuration dialog.

    :param widget_tree: Widget info dicts from the snapshot.
    :returns: True if a config dialog is detected.
    """
    for w in widget_tree:
        cls = w.get("cls", "")
        name = (w.get("object_name") or "").lower()
        text = (w.get("text") or "").lower()
        if "WindowConfig" in cls:
            return True
        if "OptionsDialog" in cls or "ConfigDialog" in cls:
            return True
        if "config" in name and "Dialog" in cls:
            return True
        if "general configuration" in text:
            return True
    return False


def _has_engine_manager(widget_tree: list[dict[str, Any]]) -> bool:
    """Return True if an engine-game manager widget is visible.

    :param widget_tree: Widget info dicts from the snapshot.
    :returns: True if the engine game panel is active.
    """
    for w in widget_tree:
        cls = w.get("cls", "")
        name = (w.get("object_name") or "").lower()
        if "ManagerPlayAgainst" in cls or "EngineManager" in cls:
            return True
        if "play_against" in name or "engine_manager" in name:
            return True
        # Marker set by FakeDriver worlds and rc game_info
        if w.get("manager_class") in ("ManagerPlayAgainstEngine",):
            return True
    return False


def _has_any_manager(widget_tree: list[dict[str, Any]]) -> bool:
    """Return True if any non-home manager is active.

    :param widget_tree: Widget info dicts from the snapshot.
    :returns: True if a manager panel (game, training, analysis, etc.) is visible.
    """
    for w in widget_tree:
        cls = w.get("cls", "")
        name = (w.get("object_name") or "").lower()
        if "Manager" in cls and cls != "ManagerBase":
            return True
        if "manager" in name:
            return True
        if w.get("manager_class"):
            return True
    return False


def _engine_is_thinking(widget_tree: list[dict[str, Any]]) -> bool:
    """Return True if the engine is currently calculating.

    :param widget_tree: Widget info dicts from the snapshot.
    :returns: True if the engine-thinking indicator is visible.
    """
    for w in widget_tree:
        if w.get("engine_thinking"):
            return True
        text = (w.get("text") or "").lower()
        cls = w.get("cls", "")
        if "thinking" in text and "Label" in cls:
            return True
    return False


def _game_is_over(widget_tree: list[dict[str, Any]]) -> bool:
    """Return True if the active game has reached a terminal state.

    :param widget_tree: Widget info dicts from the snapshot.
    :returns: True if the game-over condition is detected.
    """
    for w in widget_tree:
        if w.get("game_over"):
            return True
        if w.get("result") in ("1-0", "0-1", "1/2-1/2", "draw", "checkmate", "resign"):
            return True
    return False


def _at_home_screen(widget_tree: list[dict[str, Any]]) -> bool:
    """Return True if the home screen (no active manager) is visible.

    The home screen shows the main toolbar without a game-manager panel.
    We treat it as home whenever no manager or dialog is active.

    :param widget_tree: Widget info dicts from the snapshot.
    :returns: True if the home screen is detected.
    """
    for w in widget_tree:
        if w.get("at_home"):
            return True
        cls = w.get("cls", "")
        name = (w.get("object_name") or "").lower()
        if cls == "WBase" or "main_window" in name:
            return True
    return False


def recognise(snapshot: Snapshot) -> str:
    """Return the most specific state matching the current snapshot.

    Recognition is **dialog-first**: a modal dialog is always recognised before the
    background manager state, because a dialog blocks all other actuation.

    :param snapshot: Current app snapshot.
    :returns: One of the 8 state constants.
    """
    tree = snapshot.widget_tree

    if _any_modal_dialog(tree):
        if _is_config_dialog(tree):
            logger.debug("recognise → %s", DIALOG_CONFIG)
            return DIALOG_CONFIG
        logger.debug("recognise → %s", DIALOG_OTHER)
        return DIALOG_OTHER

    if _game_is_over(tree):
        logger.debug("recognise → %s", GAME_OVER)
        return GAME_OVER

    if _engine_is_thinking(tree):
        logger.debug("recognise → %s", ENGINE_THINKING)
        return ENGINE_THINKING

    if _has_engine_manager(tree):
        logger.debug("recognise → %s", PLAYING)
        return PLAYING

    if _has_any_manager(tree):
        logger.debug("recognise → %s", MANAGER_OTHER)
        return MANAGER_OTHER

    if _at_home_screen(tree) or not tree:
        logger.debug("recognise → %s", HOME)
        return HOME

    logger.debug("recognise → %s (no condition matched)", UNKNOWN)
    return UNKNOWN


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Transition:
    """A single directed edge in the state graph.

    :param source: Source state constant.
    :param target: Target state constant.
    :param name: Short action name used in journals and error messages.
    :param cost: Dijkstra edge weight. Higher cost = less preferred path.
    :param min_settle_ms: Milliseconds the runner must wait after this transition before
        issuing the next actuation. ``force_cancel`` edges **must** declare >= 600 ms
        (the deferred ``proc.start(300ms)`` window documented in ``QtDriver.force_cancel``).
    :param action: Optional action key to pass to ``driver.trigger_action()``.
    :param verify: Optional callable ``(snapshot: Snapshot) -> bool`` used by the runner
        to confirm the transition succeeded. ``None`` means the runner checks that the
        recognised state equals ``target``.
    """

    source: str
    target: str
    name: str
    cost: int
    min_settle_ms: int
    action: str | None = None
    verify: Callable[[Snapshot], bool] | None = dataclasses.field(
        default=None, compare=False, hash=False
    )


# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------

TRANSITION_TABLE: list[Transition] = [
    # Dialog → HOME: always try the cheap cancel path first
    Transition(
        source=DIALOG_CONFIG,
        target=HOME,
        name="dialog_cancel",
        cost=1,
        min_settle_ms=100,
        action="Cancel",
    ),
    Transition(
        source=DIALOG_OTHER,
        target=HOME,
        name="dialog_cancel",
        cost=1,
        min_settle_ms=100,
        action="Cancel",
    ),
    # Game over → HOME
    Transition(
        source=GAME_OVER,
        target=HOME,
        name="new_game_home",
        cost=2,
        min_settle_ms=200,
        action="Home",
    ),
    # Engine states → HOME: force_cancel; costs 10; min_settle >= 600 (REQUIRED)
    Transition(
        source=ENGINE_THINKING,
        target=HOME,
        name="force_cancel",
        cost=10,
        min_settle_ms=600,
        action="ForceCancel",
    ),
    Transition(
        source=PLAYING,
        target=HOME,
        name="force_cancel",
        cost=10,
        min_settle_ms=600,
        action="ForceCancel",
    ),
    Transition(
        source=MANAGER_OTHER,
        target=HOME,
        name="force_cancel",
        cost=10,
        min_settle_ms=600,
        action="ForceCancel",
    ),
    # UNKNOWN → HOME: highest cost force_cancel
    Transition(
        source=UNKNOWN,
        target=HOME,
        name="force_cancel",
        cost=15,
        min_settle_ms=600,
        action="ForceCancel",
    ),
    # HOME → game states
    Transition(
        source=HOME,
        target=PLAYING,
        name="start_game",
        cost=3,
        min_settle_ms=300,
        action="Play",
    ),
    Transition(
        source=HOME,
        target=DIALOG_CONFIG,
        name="open_config",
        cost=1,
        min_settle_ms=100,
        action="Options",
    ),
]


# ---------------------------------------------------------------------------
# StateGraph
# ---------------------------------------------------------------------------

class StateGraph:
    """Directed weighted graph over the 8 app states with Dijkstra path planning.

    :param transitions: Transition table; defaults to :data:`TRANSITION_TABLE`.
    """

    def __init__(self, transitions: list[Transition] | None = None) -> None:
        """Initialise the graph from a list of transitions.

        :param transitions: Transitions to load. Defaults to ``TRANSITION_TABLE``.
        """
        self._transitions: list[Transition] = transitions if transitions is not None else TRANSITION_TABLE
        # Adjacency list: source → list of Transition
        self._adj: dict[str, list[Transition]] = {}
        for t in self._transitions:
            self._adj.setdefault(t.source, []).append(t)

    def edges_from(self, state: str) -> list[Transition]:
        """Return all outgoing transitions from *state*.

        :param state: Source state constant.
        :returns: List of :class:`Transition` objects with this source.
        """
        return self._adj.get(state, [])

    def plan(self, from_state: str, to_state: str) -> list[Transition]:
        """Return the minimum-cost path from *from_state* to *to_state*.

        Uses Dijkstra's algorithm on transition costs.  The result is the ordered
        list of transitions to execute; an empty list means ``from_state == to_state``
        (already there).

        :param from_state: Starting state constant.
        :param to_state: Desired destination state constant.
        :returns: Ordered list of :class:`Transition` objects (may be empty).
        :raises ConvergeError: If no path exists.
        """
        if from_state == to_state:
            return []

        # Dijkstra: (cost_so_far, state, path_so_far)
        heap: list[tuple[int, str, list[Transition]]] = [(0, from_state, [])]
        visited: set[str] = set()

        while heap:
            cost, state, path = heapq.heappop(heap)
            if state in visited:
                continue
            visited.add(state)

            if state == to_state:
                return path

            for t in self.edges_from(state):
                if t.target not in visited:
                    heapq.heappush(heap, (cost + t.cost, t.target, path + [t]))

        raise ConvergeError(
            f"No path from {from_state!r} to {to_state!r} in the state graph."
        )

    def reachable_from(self, state: str) -> set[str]:
        """Return all states reachable from *state* (including *state* itself).

        :param state: Starting state.
        :returns: Set of reachable state constants.
        """
        reachable = {state}
        queue = [state]
        while queue:
            current = queue.pop()
            for t in self.edges_from(current):
                if t.target not in reachable:
                    reachable.add(t.target)
                    queue.append(t.target)
        return reachable


# Module-level default graph — shared instance for production use
DEFAULT_GRAPH: StateGraph = StateGraph()
