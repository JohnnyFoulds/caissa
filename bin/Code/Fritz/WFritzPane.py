"""
bin/Code/Fritz/WFritzPane.py — Fritz-style pane wrapper with gradient title bar.

Each Fritz right-column pane is a ``WFritzPane`` that wraps an arbitrary content
widget with a thin gradient title bar showing the pane name and `▾ ✕` buttons.

QSS / E1-E4 contract
~~~~~~~~~~~~~~~~~~~~~
Selector ``WFritzPane`` carries the gradient colour and metric properties::

    WFritzPane
    {
    qproperty-titleHeight: 20;
    qproperty-titleTop:    #3c3c3c;
    qproperty-titleBottom: #2d2d2d;
    qproperty-titlePadX:   6;
    background-color:      #1e1e1e;
    border:                1px solid #505050;
    }

Font, text colour and button styling come through ``#WFritzPaneTitle``::

    #WFritzPaneTitle { font-size: 8pt; font-weight: bold; color: #cccccc; }

:spec: §5.3, Phase 3 (feature_spec.md)
:purity: Qt allowlist — imports PySide6
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

from Code.Fritz.Types import PaneSpec

_log = logging.getLogger(__name__)


class WFritzPane(QtWidgets.QWidget):
    """Pane wrapper: gradient title bar + arbitrary content.

    :param spec: Identity and sizing policy for this pane.
    :param content: Widget to display below the title bar.
    :param parent: Optional Qt parent widget.

    :spec: §5.3
    """

    # ── E1: design values from QSS ────────────────────────────────────────────

    def _get_title_height(self) -> int:
        return self._title_height

    def _set_title_height(self, v: int) -> None:
        self._title_height = v
        self._title_bar.setFixedHeight(v)

    titleHeight = QtCore.Property(int, _get_title_height, _set_title_height)

    def _get_title_top(self) -> QtGui.QColor:
        return self._title_top

    def _set_title_top(self, c: QtGui.QColor) -> None:
        self._title_top = c
        self._title_bar.update()

    titleTop = QtCore.Property(QtGui.QColor, _get_title_top, _set_title_top)

    def _get_title_bottom(self) -> QtGui.QColor:
        return self._title_bottom

    def _set_title_bottom(self, c: QtGui.QColor) -> None:
        self._title_bottom = c
        self._title_bar.update()

    titleBottom = QtCore.Property(QtGui.QColor, _get_title_bottom, _set_title_bottom)

    def _get_title_pad_x(self) -> int:
        return self._title_pad_x

    def _set_title_pad_x(self, v: int) -> None:
        self._title_pad_x = v
        self._title_bar.layout().setContentsMargins(v, 0, 4, 0)

    titlePadX = QtCore.Property(int, _get_title_pad_x, _set_title_pad_x)

    # ── construction ──────────────────────────────────────────────────────────

    def __init__(
        self,
        spec: PaneSpec,
        content: QtWidgets.QWidget,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spec = spec
        self._content = content
        self._pane_api: dict | None = None

        # E1 defaults (light Fritz palette values; QSS overrides at polish time)
        self._title_height: int = 20
        self._title_top: QtGui.QColor = QtGui.QColor("#3c3c3c")
        self._title_bottom: QtGui.QColor = QtGui.QColor("#2d2d2d")
        self._title_pad_x: int = 6

        # E2: box model from QSS
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName(f"WFritzPane_{spec.key}")

        # Build title bar
        self._title_bar = _PaneTitleBar(spec.label, self)
        self._title_bar.setObjectName("WFritzPaneTitle")

        # Layout: title bar (fixed) above content (stretchy)
        ly = QtWidgets.QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)
        ly.addWidget(self._title_bar)
        ly.addWidget(content, 1)

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def spec(self) -> PaneSpec:
        """The ``PaneSpec`` this pane was constructed from."""
        return self._spec

    @property
    def content(self) -> QtWidgets.QWidget:
        """The wrapped content widget."""
        return self._content

    # ── wiring ────────────────────────────────────────────────────────────────

    def wire_pane_api(self, api: dict, sibling_specs: list[PaneSpec]) -> None:
        """Connect the `▾` and `✕` buttons to the pane API.

        :param api: Dict with keys ``"names"``, ``"get"``, ``"set"`` — returned
                    by ``modern_fritz_ui.pane_api(mw)``.
        :param sibling_specs: Ordered list of all pane specs (including this
                              pane), used to populate the `▾` menu's
                              Panes submenu.
        :spec: §5.3
        """
        self._pane_api = api
        self._title_bar.wire(api, self._spec, sibling_specs)

    # ── E2: paintEvent so QSS background/border renders ───────────────────────

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        p = QtGui.QPainter(self)
        self.style().drawPrimitive(
            QtWidgets.QStyle.PrimitiveElement.PE_Widget, opt, p, self
        )


# ── internal title-bar widget ─────────────────────────────────────────────────


class _PaneTitleBar(QtWidgets.QWidget):
    """Gradient title bar: pane name on the left, `▾ ✕` buttons on the right.

    Design values (gradient colours, height) are read from the parent
    ``WFritzPane``'s properties so they arrive from the ``.qss`` via E1.
    Font, text colour, and button hover states come from the
    ``#WFritzPaneTitle`` QSS selector (E2/E3).

    :spec: §5.3
    """

    def __init__(self, label: str, parent: WFritzPane) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(parent._title_height)

        self._label_widget = QtWidgets.QLabel(label, self)
        self._label_widget.setObjectName("WFritzPaneTitleLabel")

        self._btn_menu = QtWidgets.QToolButton(self)
        self._btn_menu.setText("▾")
        self._btn_menu.setFixedSize(16, 16)
        self._btn_menu.setAutoRaise(True)
        self._btn_menu.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )

        self._btn_close = QtWidgets.QToolButton(self)
        self._btn_close.setText("✕")
        self._btn_close.setFixedSize(16, 16)
        self._btn_close.setAutoRaise(True)
        self._btn_close.clicked.connect(self._on_close)

        ly = QtWidgets.QHBoxLayout(self)
        ly.setContentsMargins(parent._title_pad_x, 0, 4, 0)
        ly.setSpacing(2)
        ly.addWidget(self._label_widget)
        ly.addStretch()
        ly.addWidget(self._btn_menu)
        ly.addWidget(self._btn_close)

    # ── button wiring ─────────────────────────────────────────────────────────

    def wire(
        self,
        api: dict,
        spec: PaneSpec,
        sibling_specs: list[PaneSpec],
    ) -> None:
        """Build and attach the `▾` popup menu."""
        menu = QtWidgets.QMenu(self)

        hide_action = menu.addAction("Hide")
        hide_action.triggered.connect(lambda: api["set"](spec.key, False))

        reset_action = menu.addAction("Reset size")
        reset_action.triggered.connect(lambda: self._on_reset_size(api, spec))

        if sibling_specs:
            panes_menu = menu.addMenu("Panes")
            for s in sibling_specs:
                act = panes_menu.addAction(s.label)
                act.setCheckable(True)
                act.setChecked(bool(api["get"](s.key)))
                # Capture s by default-arg to avoid closure-over-loop-variable
                act.triggered.connect(
                    lambda checked, k=s.key: api["set"](k, checked)
                )

        self._btn_menu.setMenu(menu)

    def _on_close(self) -> None:
        pane: WFritzPane = self.parent()  # type: ignore[assignment]
        if pane._pane_api is not None:
            pane._pane_api["set"](pane._spec.key, False)
        else:
            pane.hide()

    def _on_reset_size(self, api: dict, spec: PaneSpec) -> None:
        """Reset the pane to its default_px height."""
        pane: WFritzPane = self.parent()  # type: ignore[assignment]
        right_col = pane.parent()
        if not isinstance(right_col, QtWidgets.QSplitter):
            return
        sizes = right_col.sizes()
        for i in range(right_col.count()):
            if right_col.widget(i) is pane:
                new_sizes = list(sizes)
                new_sizes[i] = spec.default_px
                right_col.setSizes(new_sizes)
                return

    # ── E2 + gradient paint ────────────────────────────────────────────────────

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        """Paint QSS box model (E2) then the gradient on top."""
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        p = QtGui.QPainter(self)
        # E2: draw QSS background-color / border-radius beneath our painting
        self.style().drawPrimitive(
            QtWidgets.QStyle.PrimitiveElement.PE_Widget, opt, p, self
        )
        # Gradient — colours arrive via E1 from the parent WFritzPane
        pane: WFritzPane = self.parent()  # type: ignore[assignment]
        grad = QtGui.QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, pane._title_top)
        grad.setColorAt(1, pane._title_bottom)
        p.fillRect(self.rect(), grad)
        p.end()
