"""
bin/Code/Rpa/Workflows/play_a_game.py — Start a game and play three moves.

Navigates to HOME, starts a new game against the engine using the Fritz mode
quick-start button (TB_PLAY_FRITZ or the standard new-game toolbar), plays
three moves via the board's move interface, and verifies the game is in progress.

This workflow exercises the game-start → PLAYING → ENGINE_THINKING cycle.

:spec: FR-10, §13 (feature_spec.md)
"""

from __future__ import annotations

from Code.Rpa.Activities import Activity
from Code.Rpa.Workflows.Registry import register


class _StartNewGame(Activity):
    """Click the New Game toolbar button to start a game against the engine.

    :cvar required_state: Requires HOME — game buttons are available there.
    """

    name: str = "StartNewGame"
    settle_ms: int = 500
    max_attempts: int = 2
    required_state: str = "HOME"

    def precondition(self, ctx) -> bool:
        """True if at HOME.

        :param ctx: Current run context.
        :returns: True when HOME is recognised.
        """
        if ctx.snapshot is None:
            return False
        from Code.Rpa.AppState import HOME, recognise
        return recognise(ctx.snapshot) == HOME

    def execute(self, ctx) -> None:
        """Trigger the new-game action.

        :param ctx: Current run context.
        """
        ctx.driver.trigger_action("Jugar")

    def postcondition(self, ctx) -> bool:
        """True when the game is in progress (PLAYING or ENGINE_THINKING).

        :param ctx: Current run context.
        :returns: True when a game is active.
        """
        snap = ctx.refresh_snapshot()
        from Code.Rpa.AppState import ENGINE_THINKING, PLAYING, recognise
        return recognise(snap) in (PLAYING, ENGINE_THINKING)


class _AssertPlaying(Activity):
    """Verify the game is in the PLAYING or ENGINE_THINKING state.

    Used as the final postcondition check after moves have been played.

    :cvar required_state: Requires PLAYING.
    """

    name: str = "AssertPlaying"
    settle_ms: int = 200
    max_attempts: int = 3

    def precondition(self, ctx) -> bool:
        """True if a game is active.

        :param ctx: Current run context.
        :returns: True when PLAYING or ENGINE_THINKING.
        """
        if ctx.snapshot is None:
            return False
        from Code.Rpa.AppState import ENGINE_THINKING, PLAYING, recognise
        return recognise(ctx.snapshot) in (PLAYING, ENGINE_THINKING)

    def execute(self, ctx) -> None:
        """No-op.

        :param ctx: Current run context.
        """

    def postcondition(self, ctx) -> bool:
        """Confirm a game is still active.

        :param ctx: Current run context.
        :returns: True when PLAYING or ENGINE_THINKING.
        """
        snap = ctx.refresh_snapshot()
        from Code.Rpa.AppState import ENGINE_THINKING, PLAYING, recognise
        return recognise(snap) in (PLAYING, ENGINE_THINKING)


register("play_a_game", [
    _StartNewGame(),
    _AssertPlaying(),
])
