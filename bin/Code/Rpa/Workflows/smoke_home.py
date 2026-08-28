"""
bin/Code/Rpa/Workflows/smoke_home.py — Smoke test: converge to HOME and verify.

Navigates the app to HOME state (using the state graph's convergence machinery
if required) and asserts it is actually there.  This is the simplest possible
end-to-end sanity check that the RPA layer, driver, and app are all alive.

:spec: FR-10, §13 (feature_spec.md)
"""

from __future__ import annotations

from Code.Rpa.Activities import Activity
from Code.Rpa.Workflows.Registry import register


class _AssertAtHome(Activity):
    """Verify the app is at HOME state, converging there if necessary.

    Setting :attr:`required_state` to ``"HOME"`` causes the Runner to use the
    state graph to drive the app home when :meth:`precondition` returns ``False``.
    """

    name: str = "AssertAtHome"
    settle_ms: int = 300
    max_attempts: int = 1
    required_state: str = "HOME"

    def precondition(self, ctx) -> bool:
        """True if the app is currently at HOME.

        :param ctx: Current run context.
        :returns: True when HOME is recognised.
        """
        if ctx.snapshot is None:
            return False
        from Code.Rpa.AppState import HOME, recognise
        return recognise(ctx.snapshot) == HOME

    def execute(self, ctx) -> None:
        """No-op — convergence already placed us at HOME.

        :param ctx: Current run context.
        """

    def postcondition(self, ctx) -> bool:
        """Confirm the app is still at HOME after the no-op execute.

        :param ctx: Current run context.
        :returns: True when HOME is confirmed.
        """
        snap = ctx.refresh_snapshot()
        from Code.Rpa.AppState import HOME, recognise
        return recognise(snap) == HOME


register("smoke_home", [_AssertAtHome()])
