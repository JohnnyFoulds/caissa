"""
coach_home.py — "caissa:coach_home" action.

Landing screen for Coach mode: four large cards that each dispatch into
an existing menu action without duplicating any handler code.
"""
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt


def register(reg):
    from Code.QT import Iconos
    reg("caissa:coach_home", _("Coach"), Iconos.Entrenamiento(), _handler)


def _handler():
    import Code
    win = _CoachHome(Code.procesador.main_window)
    action = win.exec_and_get()
    if action:
        action()


class _CoachHome(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
        )
        from Code.QT import Colocacion, Iconos

        self.setWindowTitle(_("Coach"))
        self.setWindowIcon(Iconos.Entrenamiento())
        self._action = None

        def make_card(icon, title, desc, cb):
            btn = QtWidgets.QToolButton(self)
            btn.setIcon(icon)
            btn.setIconSize(QtCore.QSize(48, 48))
            btn.setText(f"{title}\n{desc}")
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setFixedSize(190, 130)
            btn.clicked.connect(lambda checked=False, f=cb: self._pick(f))
            return btn

        card_play = make_card(
            Iconos.Libre(),
            _("Play a Game"),
            _("Face Maia with coaching"),
            self._do_play,
        )
        card_puzzle = make_card(
            Iconos.DailyTest(),
            _("Daily Puzzle"),
            _("Your daily test"),
            self._do_daily,
        )
        card_mistakes = make_card(
            Iconos.Leitner(),
            _("Review Mistakes"),
            _("Leitner spaced repetition"),
            self._do_leitner,
        )
        card_openings = make_card(
            Iconos.OpeningLines(),
            _("Opening Lines"),
            _("Drill an opening"),
            self._do_openings,
        )

        ly = Colocacion.G()
        ly.controlc(card_play,     0, 0)
        ly.controlc(card_puzzle,   0, 1)
        ly.controlc(card_mistakes, 1, 0)
        ly.controlc(card_openings, 1, 1)
        ly.margen(20)
        self.setLayout(ly)

    def _pick(self, cb):
        self._action = cb
        self.accept()

    def exec_and_get(self):
        if self.exec():
            return self._action
        return None

    def _do_play(self):
        _run("play", "free")

    def _do_daily(self):
        _run("train", "dailytest")

    def _do_leitner(self):
        _run("train", "leitner")

    def _do_openings(self):
        _run("tools", "openings_lines")


def _run(menu_name, key):
    """Dispatch key through the owning menu's run_exec — same path as Shortcuts."""
    import Code
    from Code.Shortcuts import Shortcuts
    sh = Shortcuts.Shortcuts(Code.procesador)
    getattr(sh, f"{menu_name}_menu")().run_exec(key)
