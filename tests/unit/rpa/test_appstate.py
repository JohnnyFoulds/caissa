"""
Phase 4 — AppState recogniser, Transition, and StateGraph unit tests.

All tests are pure Python — no Qt, no PySide6.

:spec: FR-5, §7 (feature_spec.md)
"""

import pytest

pytestmark = pytest.mark.rpa

from Code.Rpa.AppState import (
    DEFAULT_GRAPH,
    ALL_STATES,
    DIALOG_CONFIG,
    DIALOG_OTHER,
    ENGINE_THINKING,
    GAME_OVER,
    HOME,
    MANAGER_OTHER,
    PLAYING,
    TRANSITION_TABLE,
    UNKNOWN,
    StateGraph,
    Transition,
    recognise,
)
from Code.Rpa.Errors import ConvergeError
from Code.Rpa.Types import Snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(*widgets) -> Snapshot:
    """Build a Snapshot with the given widget dicts."""
    return Snapshot(state_name="UNKNOWN", widget_tree=list(widgets), timestamp_ms=0.0)


def _empty_snap() -> Snapshot:
    """Empty snapshot — no widgets at all."""
    return Snapshot(state_name="UNKNOWN", widget_tree=[], timestamp_ms=0.0)


# ---------------------------------------------------------------------------
# Recogniser — basic cases
# ---------------------------------------------------------------------------

def test_recognise_home_on_empty_tree():
    """Empty widget tree → HOME (no manager, no dialog)."""
    assert recognise(_empty_snap()) == HOME


def test_recognise_home():
    """WBase main window widget → HOME."""
    snap = _snap({"cls": "WBase", "visible": True})
    assert recognise(snap) == HOME


def test_recognise_unknown_fallback():
    """Unrecognised widget with no special markers → UNKNOWN."""
    snap = _snap({"cls": "QSomeWidget", "visible": True})
    assert recognise(snap) == UNKNOWN


def test_recognise_dialog_config_priority():
    """WindowConfig dialog → DIALOG_CONFIG even when engine manager is also present."""
    snap = _snap(
        {"cls": "WindowConfig", "visible": True, "modal": True},
        {"cls": "ManagerPlayAgainstEngine", "visible": True},
    )
    assert recognise(snap) == DIALOG_CONFIG


def test_recognise_dialog_config_by_class():
    """Widget class 'WindowConfig' alone triggers DIALOG_CONFIG."""
    snap = _snap({"cls": "WindowConfig", "visible": True})
    assert recognise(snap) == DIALOG_CONFIG


def test_recognise_dialog_other():
    """A generic Dialog class (not config) → DIALOG_OTHER."""
    snap = _snap({"cls": "QDialog", "modal": True, "visible": True})
    assert recognise(snap) == DIALOG_OTHER


def test_recognise_dialog_other_by_modal_flag():
    """A widget with modal=True → DIALOG_OTHER when it is not a config dialog."""
    snap = _snap({"cls": "WFritzNewGame", "modal": True, "visible": True})
    assert recognise(snap) == DIALOG_OTHER


def test_recognise_game_over():
    """game_over=True flag → GAME_OVER (no dialog present)."""
    snap = _snap({"cls": "QWidget", "visible": True, "game_over": True})
    assert recognise(snap) == GAME_OVER


def test_recognise_engine_thinking():
    """engine_thinking=True flag → ENGINE_THINKING."""
    snap = _snap({"cls": "QWidget", "visible": True, "engine_thinking": True})
    assert recognise(snap) == ENGINE_THINKING


def test_recognise_playing():
    """ManagerPlayAgainstEngine class → PLAYING (no thinking flag)."""
    snap = _snap({"cls": "ManagerPlayAgainstEngine", "visible": True})
    assert recognise(snap) == PLAYING


def test_recognise_manager_other():
    """A non-engine manager class → MANAGER_OTHER."""
    snap = _snap({"cls": "ManagerAnalysis", "visible": True})
    assert recognise(snap) == MANAGER_OTHER


def test_recognise_dialog_takes_priority_over_game_over():
    """A dialog present alongside game_over → DIALOG_OTHER (dialog wins)."""
    snap = _snap(
        {"cls": "QDialog", "modal": True, "visible": True},
        {"cls": "QWidget", "game_over": True, "visible": True},
    )
    assert recognise(snap) == DIALOG_OTHER


def test_recognise_engine_thinking_takes_priority_over_playing():
    """engine_thinking flag wins over bare engine manager detection."""
    snap = _snap(
        {"cls": "ManagerPlayAgainstEngine", "visible": True, "engine_thinking": True},
    )
    assert recognise(snap) == ENGINE_THINKING


# ---------------------------------------------------------------------------
# Transition table invariants
# ---------------------------------------------------------------------------

def test_every_force_cancel_edge_declares_min_settle_at_least_600():
    """All force_cancel transitions must have min_settle_ms >= 600.

    This is a load-bearing invariant: force_cancel defers proc.start by 300 ms
    and the runner must not issue a follow-up actuation before that window elapses.
    """
    for t in TRANSITION_TABLE:
        if t.name == "force_cancel":
            assert t.min_settle_ms >= 600, (
                f"Transition {t.source!r} → {t.target!r} via {t.name!r} "
                f"declares only {t.min_settle_ms} ms settle (< 600)."
            )


def test_all_transition_sources_and_targets_are_known_states():
    """Every source and target in the table is one of the 8 known state constants."""
    for t in TRANSITION_TABLE:
        assert t.source in ALL_STATES, f"Unknown source state: {t.source!r}"
        assert t.target in ALL_STATES, f"Unknown target state: {t.target!r}"


def test_transition_costs_are_positive():
    """Every transition has a cost > 0."""
    for t in TRANSITION_TABLE:
        assert t.cost > 0, f"Transition {t.name!r} has cost {t.cost}"


def test_transition_min_settle_is_non_negative():
    """Every transition has min_settle_ms >= 0."""
    for t in TRANSITION_TABLE:
        assert t.min_settle_ms >= 0, f"Transition {t.name!r} has negative settle"


# ---------------------------------------------------------------------------
# StateGraph — Dijkstra planning
# ---------------------------------------------------------------------------

def test_plan_same_state_returns_empty():
    """plan(HOME, HOME) returns an empty list."""
    assert DEFAULT_GRAPH.plan(HOME, HOME) == []


def test_plan_home_to_playing():
    """plan(HOME, PLAYING) returns a non-empty path with the start_game transition."""
    path = DEFAULT_GRAPH.plan(HOME, PLAYING)
    assert len(path) >= 1
    assert path[0].source == HOME
    assert path[-1].target == PLAYING


def test_plan_dialog_config_to_home():
    """plan(DIALOG_CONFIG, HOME) uses the cheap dialog_cancel path."""
    path = DEFAULT_GRAPH.plan(DIALOG_CONFIG, HOME)
    assert len(path) == 1
    assert path[0].name == "dialog_cancel"
    assert path[0].cost == 1


def test_plan_avoids_force_cancel_when_cheaper_path_exists():
    """plan(DIALOG_CONFIG, HOME) uses dialog_cancel (cost 1), not force_cancel (cost 10+)."""
    path = DEFAULT_GRAPH.plan(DIALOG_CONFIG, HOME)
    names = [t.name for t in path]
    assert "dialog_cancel" in names
    assert "force_cancel" not in names


def test_plan_engine_thinking_to_home_uses_force_cancel():
    """plan(ENGINE_THINKING, HOME) must go through force_cancel (only available edge)."""
    path = DEFAULT_GRAPH.plan(ENGINE_THINKING, HOME)
    assert len(path) >= 1
    assert any(t.name == "force_cancel" for t in path)


def test_plan_rejects_unreachable_state():
    """plan() raises ConvergeError when no path exists."""
    # Build a graph where HOME has no outgoing edges
    isolated_graph = StateGraph(transitions=[
        Transition(HOME, PLAYING, "start_game", cost=3, min_settle_ms=300),
    ])
    with pytest.raises(ConvergeError):
        isolated_graph.plan(PLAYING, HOME)


def test_every_state_can_reach_home():
    """Every state in the graph must be able to reach HOME."""
    for state in ALL_STATES:
        if state == HOME:
            continue
        try:
            path = DEFAULT_GRAPH.plan(state, HOME)
            assert isinstance(path, list), f"plan({state}, HOME) returned non-list"
        except ConvergeError as exc:
            pytest.fail(f"State {state!r} cannot reach HOME: {exc}")


def test_plan_unknown_to_home_uses_force_cancel():
    """UNKNOWN → HOME path exists and goes through force_cancel."""
    path = DEFAULT_GRAPH.plan(UNKNOWN, HOME)
    assert len(path) >= 1
    assert any(t.name == "force_cancel" for t in path)


def test_plan_returns_minimum_cost_path():
    """plan returns a path whose total cost is minimal.

    Set up a graph with two paths from A to C:
    A→B (cost 1) + B→C (cost 1) = total 2
    A→C (cost 5)                 = total 5
    """
    t_ab = Transition("A", "B", "ab", cost=1, min_settle_ms=0)
    t_bc = Transition("B", "C", "bc", cost=1, min_settle_ms=0)
    t_ac = Transition("A", "C", "ac_direct", cost=5, min_settle_ms=0)
    graph = StateGraph(transitions=[t_ab, t_bc, t_ac])
    path = graph.plan("A", "C")
    total_cost = sum(t.cost for t in path)
    assert total_cost == 2
    assert [t.name for t in path] == ["ab", "bc"]


def test_reachable_from_home():
    """reachable_from(HOME) includes at least HOME, PLAYING, and DIALOG_CONFIG."""
    reachable = DEFAULT_GRAPH.reachable_from(HOME)
    assert HOME in reachable
    assert PLAYING in reachable
    assert DIALOG_CONFIG in reachable


# ---------------------------------------------------------------------------
# StateGraph — custom transition tables
# ---------------------------------------------------------------------------

def test_state_graph_with_custom_transitions():
    """StateGraph can be initialised with a custom transition list."""
    t = Transition("X", "Y", "xy", cost=1, min_settle_ms=0)
    graph = StateGraph(transitions=[t])
    path = graph.plan("X", "Y")
    assert len(path) == 1
    assert path[0].name == "xy"


def test_state_graph_empty_table_raises_on_plan():
    """An empty graph raises ConvergeError for any non-trivial plan."""
    graph = StateGraph(transitions=[])
    with pytest.raises(ConvergeError):
        graph.plan(HOME, PLAYING)
