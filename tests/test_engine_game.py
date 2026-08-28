"""
tests/test_engine_game.py — automated tests for the Play-against-Engine flow.

Regression test for: Play > Play against engine > Accept > play a3 > nothing.

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/test_engine_game.py -v
"""
import pytest
from tests.helpers import GameDriver, build_default_dic_var, wait_until

pytestmark = pytest.mark.unit


# ── helpers ───────────────────────────────────────────────────────────────────

def _stockfish_available() -> bool:
    import os
    sf_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "bin", "OS", "darwin", "Engines", "stockfish", "stockfish-18-arm64",
    )
    return os.path.isfile(sf_path)


requires_stockfish = pytest.mark.skipif(
    not _stockfish_available(),
    reason="Stockfish arm64 binary not present",
)


# ── tests ─────────────────────────────────────────────────────────────────────

class TestEngineGameFlow:
    """Tests for the full play-against-engine flow."""

    @requires_stockfish
    def test_engine_replies_after_a3(self, minimal_procesador):
        """
        Regression: Play > engine > Accept > play a3 > engine must reply.

        This reproduces the reported bug where playing a3 resulted in 'nothing'.
        """
        driver = GameDriver(minimal_procesador)
        driver.start_game(engine_key="stockfish", is_white=True, engine_depth=1)

        # Human (White) plays 1.a3
        move_accepted = driver.play_move("a2", "a3")
        assert move_accepted, (
            "Move a2→a3 was rejected by the game manager — "
            "check check_human_move / player_has_moved_mandatory"
        )

        # The engine (Black) must reply within 15 seconds
        engine_replied = driver.wait_for_engine_reply(max_secs=15.0)
        assert engine_replied, (
            "Engine did not reply after White played a3 — "
            "check play_engine_rival / manager_rival.play() return value"
        )

        # Game should now have exactly 2 half-moves
        assert driver.game_length == 2, (
            f"Expected 2 plies after 1.a3 + engine reply, got {driver.game_length}"
        )

    @requires_stockfish
    def test_engine_replies_after_e4(self, minimal_procesador):
        """Standard 1.e4 opening move — sanity check."""
        driver = GameDriver(minimal_procesador)
        driver.start_game(engine_key="stockfish", is_white=True, engine_depth=1)

        assert driver.play_move("e2", "e4"), "1.e4 was rejected"
        assert driver.wait_for_engine_reply(max_secs=15.0), "Engine did not reply to 1.e4"
        assert driver.game_length == 2

    @requires_stockfish
    def test_multiple_moves(self, minimal_procesador):
        """Play two full move pairs and verify the game progresses."""
        driver = GameDriver(minimal_procesador)
        driver.start_game(engine_key="stockfish", is_white=True, engine_depth=1)

        # Move 1
        assert driver.play_move("e2", "e4"), "1.e4 rejected"
        assert driver.wait_for_engine_reply(max_secs=15.0), "Engine didn't reply to 1.e4"
        assert driver.game_length == 2

        # Move 2
        assert driver.play_move("d2", "d4"), "2.d4 rejected"
        assert driver.wait_for_engine_reply(max_secs=15.0), "Engine didn't reply to 2.d4"
        assert driver.game_length == 4

    @requires_stockfish
    def test_play_as_black(self, minimal_procesador):
        """Engine plays first (as White), then human plays as Black."""
        driver = GameDriver(minimal_procesador)
        driver.start_game(engine_key="stockfish", is_white=False, engine_depth=1)

        # Engine should make White's first move automatically
        engine_replied = driver.wait_for_engine_reply(max_secs=15.0)
        assert engine_replied, "Engine (White) did not make its opening move"
        assert driver.game_length == 1

        # Human plays as Black: e7→e5
        assert driver.play_move("e7", "e5"), "1...e5 rejected"
        assert driver.wait_for_engine_reply(max_secs=15.0), "Engine didn't reply to 1...e5"
        assert driver.game_length == 3


class TestDicVarConstruction:
    """Unit tests for the dic_var builder."""

    def test_default_dic_var_is_valid(self):
        """build_default_dic_var produces a dict that the manager can consume."""
        import Code
        from Code.Base.Constantes import ENG_INTERNAL

        dic = build_default_dic_var(engine_depth=1)
        assert dic["ISWHITE"] is True
        assert "RIVAL" in dic
        dr = dic["RIVAL"]
        assert dr["ENGINE_DEPTH"] == 1
        assert dr["ENGINE_TIME"] == 0
        assert dr["CM"] is not None

    def test_engine_time_scaling(self):
        """ENGINE_TIME is stored as tenths of seconds (×100 factor in the manager)."""
        dic = build_default_dic_var(engine_time_ms=5000)  # 5 seconds
        # Stored as integer tenths-of-seconds: 5000ms / 100 = 50
        assert dic["RIVAL"]["ENGINE_TIME"] == 50


class TestUIModeFilter:
    """Tests for the UIModes filter — ensure Classical mode is transparent."""

    def test_classical_allows_all_toolbar(self):
        """Classical mode must not filter any toolbar buttons."""
        from Code.UIModes import UIModes
        assert UIModes.allows_all_toolbar(), (
            "Classical mode should allow all toolbar buttons — "
            "check x_ui_mode default value and classical.json"
        )

    def test_classical_allows_cancel(self):
        """TB_CANCEL must always pass the filter (needed by closeEvent)."""
        from Code.UIModes import UIModes
        from Code.Base.Constantes import TB_CANCEL
        assert UIModes.allows_toolbar(TB_CANCEL)

    def test_never_filter_set_passes(self):
        """All NEVER_FILTER_TOOLBAR keys pass regardless of mode."""
        from Code.UIModes import UIModes
        for key in UIModes.NEVER_FILTER_TOOLBAR:
            assert UIModes.allows_toolbar(key), (
                f"TB key {key} in NEVER_FILTER_TOOLBAR was blocked by the filter"
            )

    def test_filter_menu_noop_in_classical(self, configuration):
        """filter_menu_options is a no-op in Classical mode."""
        from Code.UIModes import UIModes
        from Code.Menus import BaseMenu
        from Code.QT import Iconos

        # Build a mini menu and verify nothing is removed
        menu = BaseMenu.RootMenu.__new__(BaseMenu.RootMenu)
        menu.li_options = [
            BaseMenu.Option("free", "Play", Iconos.Libre(), False, True),
            BaseMenu.Option("databases", "Databases", Iconos.Database(), False, True),
        ]
        UIModes.filter_menu_options(menu)
        assert len(menu.li_options) == 2, "Classical filter must not remove any options"
