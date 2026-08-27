"""
tests/test_engine_responds.py — direct tests for the engine play layer.

Tests that the engine responds to game positions, without needing the full
GUI stack.  This is the direct test for the "play a3 → nothing" bug:
if the engine is broken, play() returns None and the game freezes.

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/test_engine_responds.py -v
"""
import os
import pytest


def _sf_binary():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "bin", "OS", "darwin", "Engines", "stockfish", "stockfish-18-arm64",
    )


requires_stockfish = pytest.mark.skipif(
    not os.path.isfile(_sf_binary()),
    reason="Stockfish arm64 binary not present",
)


@requires_stockfish
class TestEngineResponds:
    """
    Direct tests for EngineManagerPlay.play().

    These bypass the full game manager so we can isolate the engine layer.
    """

    def _make_stockfish_manager(self, depth: int = 1):
        import Code
        from Code.Base.Constantes import ENG_INTERNAL
        from Code.Engines import SelectEngines
        from Code import Procesador

        rival = SelectEngines.busca_engine_default(ENG_INTERNAL, "stockfish", "stockfish")
        assert rival is not None, "Stockfish engine not found in configuration"
        mgr = Procesador.Procesador.create_manager_engine(rival, 0, depth, 0)
        mgr.check_engine()
        return mgr

    def test_engine_responds_to_initial_position(self):
        """Engine must return a move from the starting position."""
        from Code.Base import Game

        mgr = self._make_stockfish_manager(depth=1)
        game = Game.Game()

        rm = mgr.play(game=game)
        assert rm is not None, (
            "Engine returned None from the initial position — "
            "engine process may have failed to start or UCI handshake failed"
        )
        assert rm.from_sq and rm.to_sq, (
            f"Engine returned incomplete move: from={rm.from_sq!r} to={rm.to_sq!r}"
        )
        if mgr.engine_run:
            mgr.engine_run.close()

    def test_engine_responds_after_a3(self):
        """
        Regression: engine must respond after White plays 1.a3.

        This is the direct reproduction of the reported bug.
        """
        from Code.Base import Game, Move

        mgr = self._make_stockfish_manager(depth=1)
        game = Game.Game()

        # Apply 1.a3 to the game
        ok, error, move = Move.get_game_move(
            game, game.last_position, "a2", "a3", ""
        )
        assert ok, f"Failed to apply 1.a3 to initial position: {error}"
        game.add_move(move)

        # Engine must respond as Black
        rm = mgr.play(game=game)
        assert rm is not None, (
            "Engine returned None after 1.a3 — this is the reported bug. "
            "Likely cause: engine process died, or play() returned early. "
            "Check EngineManagerPlay.play() and EngineRun.play()."
        )
        assert rm.from_sq and rm.to_sq, (
            f"Engine returned invalid move after 1.a3: from={rm.from_sq!r} to={rm.to_sq!r}"
        )
        if mgr.engine_run:
            mgr.engine_run.close()

    def test_engine_responds_after_e4(self):
        """Sanity check: engine responds to 1.e4."""
        from Code.Base import Game, Move

        mgr = self._make_stockfish_manager(depth=1)
        game = Game.Game()

        ok, error, move = Move.get_game_move(
            game, game.last_position, "e2", "e4", ""
        )
        assert ok, f"Failed to apply 1.e4: {error}"
        game.add_move(move)

        rm = mgr.play(game=game)
        assert rm is not None, "Engine returned None after 1.e4"
        if mgr.engine_run:
            mgr.engine_run.close()

    def test_engine_responds_twice(self):
        """Engine must respond to two consecutive positions."""
        from Code.Base import Game, Move

        mgr = self._make_stockfish_manager(depth=1)
        game = Game.Game()

        # 1.e4
        ok, _, move = Move.get_game_move(game, game.last_position, "e2", "e4", "")
        assert ok
        game.add_move(move)
        rm1 = mgr.play(game=game)
        assert rm1 is not None, "Engine didn't respond to 1.e4"

        # Apply engine's reply
        ok, _, move = Move.get_game_move(
            game, game.last_position, rm1.from_sq, rm1.to_sq, rm1.promotion or ""
        )
        assert ok, f"Engine move {rm1.from_sq}{rm1.to_sq} is invalid"
        game.add_move(move)

        # 2.d4
        ok, _, move = Move.get_game_move(game, game.last_position, "d2", "d4", "")
        assert ok
        game.add_move(move)
        rm2 = mgr.play(game=game)
        assert rm2 is not None, "Engine didn't respond to 2.d4"

        if mgr.engine_run:
            mgr.engine_run.close()

    def test_engine_manager_can_be_restarted(self):
        """Engine manager can be stopped and started for a new game."""
        from Code.Base import Game

        mgr1 = self._make_stockfish_manager(depth=1)
        game = Game.Game()
        rm = mgr1.play(game=game)
        assert rm is not None, "First game: engine didn't respond"
        if mgr1.engine_run:
            mgr1.engine_run.close()

        mgr2 = self._make_stockfish_manager(depth=1)
        rm2 = mgr2.play(game=game)
        assert rm2 is not None, "Second game: engine didn't respond after restart"
        if mgr2.engine_run:
            mgr2.engine_run.close()
