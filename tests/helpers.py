"""
tests/helpers.py — utilities for programmatically driving game managers.

These helpers let tests inject moves, wait for engine responses, and
observe game state without touching the GUI.
"""
import time
from typing import Optional, Tuple

from PySide6 import QtCore, QtWidgets


def pump_events(max_secs: float = 10.0, poll_secs: float = 0.05) -> None:
    """Process Qt events for up to max_secs, polling every poll_secs."""
    app = QtWidgets.QApplication.instance()
    deadline = time.time() + max_secs
    while time.time() < deadline:
        app.processEvents()
        time.sleep(poll_secs)


def wait_until(predicate, max_secs: float = 15.0, poll_secs: float = 0.1) -> bool:
    """
    Process Qt events until predicate() returns True or max_secs elapses.
    Returns True if predicate was satisfied, False on timeout.
    """
    app = QtWidgets.QApplication.instance()
    deadline = time.time() + max_secs
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(poll_secs)
    return False


def build_default_dic_var(
    engine_key: str = "stockfish",
    is_white: bool = True,
    engine_depth: int = 1,
    engine_time_ms: int = 0,
) -> dict:
    """
    Build a dic_var dict equivalent to clicking Accept in WPlayAgainstEngine
    with the given settings.  engine_depth=1 is the fastest config for tests.
    """
    import Code
    from Code.Base.Constantes import (
        ADJUST_BETTER, ENG_INTERNAL, BOOK_BEST_MOVE
    )
    from Code.Engines import SelectEngines

    rival = SelectEngines.busca_engine_default(ENG_INTERNAL, engine_key, engine_key)
    if rival is None:
        # Fall back to first internal engine
        rival = SelectEngines.busca_engine_default(ENG_INTERNAL, "irina", "irina")

    dr = {
        "ENGINE": rival.key,
        "TYPE": rival.type,
        "ALIAS": rival.key,
        "LIUCI": rival.liUCI,
        "ENGINE_TIME": engine_time_ms // 100,  # stored as tenths of seconds
        "ENGINE_DEPTH": engine_depth,
        "ENGINE_NODES": 0,
        "ENGINE_UNLIMITED": 1,   # 1 minute — not used when depth is set
        "CM": rival,
    }

    return {
        "ISWHITE": is_white,
        "RIVAL": dr,
        "HINTS": 0,
        "ARROWS": 0,
        "THOUGHTOP": -1,
        "THOUGHTTT": -1,
        "ARROWSTT": 0,
        "2CHANCE": False,
        "SUMMARY": False,
        "TAKEBACK": True,
        "WITHTIME": False,
        "TIME_MODE": 0,
        "MINUTES": 10.0,
        "SECONDS": 0,
        "MINEXTRA": 0,
        "ADJUST": ADJUST_BETTER,
        "LEVEL_HUMANIZE": 0,
        "WITH_LIMIT_PWW": False,
        "LIMIT_PWW": 90,
        "BOXHEIGHT": 24,
        "ACTIVATE_EBOARD": False,
        "OPENING": None,
        "OPENING_LINE": None,
        "FEN": "",
        "RESIGN": -800,
    }


class GameDriver:
    """
    Drives a ManagerPlayAgainstEngine without a real GUI.

    Usage::

        driver = GameDriver(procesador_stub)
        driver.start_game()
        assert driver.play_move("a2", "a3"), "Move rejected"
        assert driver.wait_for_engine_reply(), "Engine did not reply"
    """

    def __init__(self, procesador_stub):
        self._proc = procesador_stub
        self.manager = None
        self._engine_replied = False
        self._last_engine_move: Optional[Tuple[str, str]] = None
        self._move_count_before = 0

    def start_game(
        self,
        engine_key: str = "stockfish",
        is_white: bool = True,
        engine_depth: int = 1,
    ) -> None:
        """
        Start a Play-against-engine game programmatically.
        The manager is created and started without showing any dialog.
        """
        import Code
        from Code.PlayAgainstEngine import ManagerPlayAgainstEngine
        from Code.Base import Game

        dic_var = build_default_dic_var(
            engine_key=engine_key,
            is_white=is_white,
            engine_depth=engine_depth,
        )

        # Manager.__init__ reads procesador.main_window and procesador.board,
        # so we attach them to the stub before constructing the manager.
        main_window = _make_stub_main_window()
        self._proc.main_window = main_window
        self._proc.board = main_window.board

        mgr = ManagerPlayAgainstEngine.ManagerPlayAgainstEngine(self._proc)

        # Patch rival_has_moved to observe engine replies
        original_rhm = mgr.rival_has_moved

        def _patched_rhm(rm_rival):
            result = original_rhm(rm_rival)
            if rm_rival is not None:
                self._engine_replied = True
                self._last_engine_move = (rm_rival.from_sq, rm_rival.to_sq)
            return result

        mgr.rival_has_moved = _patched_rhm

        self.manager = mgr
        self._engine_replied = False
        self._last_engine_move = None

        mgr.start(dic_var)

    def play_move(self, from_sq: str, to_sq: str, promotion: str = "") -> bool:
        """
        Inject a player move.  Returns True if the move was accepted.
        The move is accepted when the game length increases.
        """
        if self.manager is None:
            raise RuntimeError("call start_game() first")
        before = len(self.manager.game)
        self._engine_replied = False
        self.manager.player_has_moved_dispatcher(from_sq, to_sq, promotion)
        # Wait up to 2 s for the move to register (it goes through a singleShot(0) timer)
        return wait_until(lambda: len(self.manager.game) > before, max_secs=2.0)

    def wait_for_engine_reply(self, max_secs: float = 15.0) -> bool:
        """
        Wait until the engine makes a move (or timeout).
        Returns True if the engine replied, False on timeout.
        After detecting the reply, pump one more round so play_next_move fires
        and the manager is ready to accept the next human move.
        """
        ok = wait_until(lambda: self._engine_replied, max_secs=max_secs)
        if ok:
            # play_next_move() is queued via singleShot(0); pump it now
            pump_events(max_secs=0.5, poll_secs=0.05)
        return ok

    @property
    def game_length(self) -> int:
        return len(self.manager.game) if self.manager else 0

    @property
    def last_engine_move(self) -> Optional[Tuple[str, str]]:
        return self._last_engine_move


class _AutoStub:
    """Stub that returns a noop callable for any unknown attribute."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            pass
        object.__setattr__(self, name, _noop)
        return _noop


def _make_stub_main_window():
    """
    Minimal stub for WBase / MainWindow that satisfies all attribute accesses
    the ManagerPlayAgainstEngine makes during start(), play_human(), and
    play_engine_rival().
    """

    def _noop(*args, **kwargs):
        pass

    def _noop_false(*args, **kwargs):
        return False

    def _noop_true(*args, **kwargs):
        return True

    # Board stub — auto-fills any missing method with _noop
    board_stub = _AutoStub(
        activate_side=_noop,
        set_base_position=_noop,
        set_position=_noop,
        set_dispatcher=_noop,
        remove_arrows=_noop,
        show_arrows=_noop,
        show_arrows_temp=_noop,
        show_arrow_premove=_noop,
        put_arrow_sc=_noop,
        put_arrow_scvar=_noop,
        show_pv=_noop,
        pawn_promoting=lambda *a, **k: "q",
        piece_out_position=lambda *a, **k: (False, None, None),
        dispatch_eboard=_noop,
        side_indicator_sc=_AutoStub(setVisible=_noop),
        set_side_indicator=_noop,
        variation_history=None,
        ancho=600,
        btCierre=_AutoStub(setVisible=_noop),
        pieces_are_active=False,
        last_position=None,
        is_white_bottom=True,
        escena=_AutoStub(),
    )

    # Toolbar stub
    tb_stub = _AutoStub(
        clear=_noop,
        addAction=_noop,
        setEnabled=_noop,
        update=_noop,
        toolButtonStyle=lambda: 0,
        li_acciones=[],
        widgetForAction=lambda a: _AutoStub(setToolTip=_noop),
    )

    # Clock label stubs
    clock_label = types.SimpleNamespace(
        set_text=_noop,
        setVisible=_noop,
    )

    # Main window stub — auto-fills any missing attr with _noop
    stub = _AutoStub(
        board=board_stub,
        tb=tb_stub,
        configuration=None,  # will be set below
        dic_toolbar={},
        manager=None,
        pgn=_AutoStub(
            refresh=_noop,
            goto_end=_noop,
            remove_hints=_noop,
        ),
        # Clock methods
        start_clock=_noop,
        stop_clock=_noop,
        active_game=_noop,
        set_data_clock=_noop,
        hide_clock_white=_noop,
        hide_clock_black=_noop,
        # Label methods
        set_label1=_noop,
        set_label2=_noop,
        set_label3=_noop,
        get_labels=lambda: ("", "", ""),
        set_hight_label3=_noop,
        remove_label3=_noop,
        # Toolbar / state
        pon_toolbar=_noop,
        enable_option_toolbar=_noop,
        set_activate_tutor=_noop,
        set_notify=_noop,
        pensando_tutor=_noop,
        cursor_out_board=_noop,
        # PGN
        pgn_refresh=_noop,
        pgn_pos_actual=lambda: (0, types.SimpleNamespace(key="WHITE")),
        goto_end=_noop,
        # Info / display
        show_info_extra=_noop,
        put_pieces_bottom=_noop,
        side_indicator_sc=_AutoStub(setVisible=_noop),
        set_side_indicator=_noop,
        change_player_labels=_noop,
        refresh=_noop,
        # Window management
        key_video="maind",
        accept=_noop,
        final_processes=_noop,
        base=_AutoStub(
            change_player_labels=_noop,
        ),
        # Kibitzers
        kibitzers_manager=_AutoStub(
            run_new=_noop,
            check=_noop,
        ),
        # WBase compatibility
        with_shortcuts=False,
        non_distract_mode_active=False,
        siCapturas=False,
    )

    import Code
    stub.configuration = Code.configuration
    return stub


import types
