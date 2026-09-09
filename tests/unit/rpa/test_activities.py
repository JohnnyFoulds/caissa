"""
tests/unit/rpa/test_activities.py — Activity contract matrix (Phase 9).

Every concrete activity in :mod:`Code.Rpa.Activities` must expose the runner
contract: ``precondition(ctx)`` / ``execute(ctx)`` / ``postcondition(ctx)``
plus ``settle_ms`` / ``max_attempts`` attributes. ``Click``, ``Sequence``,
and ``RetryScope`` are exercised here with the real classes over
``FakeDriver`` + ``FakeClock`` — no synthetic doubles.

:spec: FR-2, §5
"""
import inspect

import pytest

pytestmark = pytest.mark.rpa

from Code.Rpa.Activities import Activity, Click, Context, RetryScope, Sequence
from Code.Rpa.AppState import DEFAULT_GRAPH, HOME
from Code.Rpa.Fakes import FakeClock, FakeDriver, World
from Code.Rpa.Types import Snapshot


def _ctx_with_tree(tree: list[dict] | None) -> tuple[Context, FakeDriver]:
    """Build a Context whose snapshot holds *tree* (None = no snapshot yet)."""
    clock = FakeClock(start_ms=0.0)
    world = World(current_state=HOME, widget_trees={HOME: tree or []})
    driver = FakeDriver(world=world, clock=clock)
    ctx = Context(driver=driver, graph=DEFAULT_GRAPH, run_id="r-act-0001")
    ctx.snapshot = (
        Snapshot(state_name=HOME, widget_tree=tree or [], timestamp_ms=0.0)
        if tree is not None
        else None
    )
    return ctx, driver


def _concrete_activities() -> list[type[Activity]]:
    """Return all concrete Activity subclasses defined in Activities.py."""
    import Code.Rpa.Activities as mod

    found = []
    for _, obj in inspect.getmembers(mod, predicate=inspect.isclass):
        if obj is Activity or not issubclass(obj, Activity):
            continue
        if obj.__module__ != mod.__name__:
            continue
        if obj in (Sequence, RetryScope):
            found.append(obj)
            continue
        try:
            obj.__new__(obj)
        except Exception:
            continue
        found.append(obj)
    return found


def test_every_concrete_activity_exposes_ctx_contract():
    """Concrete activities override pre/execute/post(ctx) and declare timing attrs."""
    for cls in _concrete_activities():
        for method in ("precondition", "execute", "postcondition"):
            assert method in cls.__dict__ or any(
                method in base.__dict__ for base in cls.__mro__[1:]
            ), f"{cls.__name__} missing {method}"
            sig = inspect.signature(getattr(cls, method))
            params = list(sig.parameters)
            assert params[:2] == ["self", "ctx"], (
                f"{cls.__name__}.{method} must take (self, ctx), got {params}"
            )
        assert isinstance(cls.settle_ms, int), f"{cls.__name__}.settle_ms must be int"
        assert isinstance(cls.max_attempts, int), f"{cls.__name__}.max_attempts must be int"


def test_click_full_matrix_visible_target():
    """Click: precondition True, execute issues one click, postcondition True."""
    tree = [{"cls": "QPushButton", "object_name": "Play", "text": "Play", "visible": True}]
    ctx, driver = _ctx_with_tree(tree)
    act = Click("Play")
    assert act.precondition(ctx) is True
    act.execute(ctx)
    assert driver.calls == [{"method": "click", "selector": "Play", "target_type": "widget"}]
    assert act.postcondition(ctx) is True


def test_click_precondition_false_without_snapshot_or_when_hidden():
    """Click refuses to run with no snapshot or a hidden target."""
    ctx, _ = _ctx_with_tree(None)
    assert Click("Play").precondition(ctx) is False
    hidden = [{"cls": "QPushButton", "object_name": "Play", "text": "Play", "visible": False}]
    ctx2, _ = _ctx_with_tree(hidden)
    assert Click("Play").precondition(ctx2) is False


def test_click_execute_issues_single_driver_action():
    """Click.execute performs exactly one driver call and nothing else."""
    tree = [{"cls": "QPushButton", "object_name": "Go", "text": "Go", "visible": True}]
    ctx, driver = _ctx_with_tree(tree)
    Click("Go", settle_ms=50).execute(ctx)
    assert len(driver.calls) == 1
    assert driver.calls[0]["method"] == "click"


def test_sequence_contract_and_order():
    """Sequence keeps sub-activity order, is unconditional, and actuates nothing itself."""
    inner = [Click("A"), Click("B")]
    seq = Sequence(inner)
    assert list(seq.activities) == inner
    ctx, driver = _ctx_with_tree([])
    assert seq.precondition(ctx) is True
    seq.execute(ctx)
    assert driver.calls == []
    assert seq.postcondition(ctx) is True


def test_retry_scope_contract():
    """RetryScope stores attempts, is unconditional, and actuates nothing itself."""
    scope = RetryScope([Click("A")], max_attempts=3)
    assert scope.max_attempts == 3
    ctx, driver = _ctx_with_tree([])
    assert scope.precondition(ctx) is True
    scope.execute(ctx)
    assert driver.calls == []
    assert scope.postcondition(ctx) is True
