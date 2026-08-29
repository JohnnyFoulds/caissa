"""
bin/Code/Fritz/WDropdownPanel.py — Fritz-style floating dropdown panel.

Purity tier: **Qt allowlist**
:spec: §5.2 (feature_spec.md)
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

from Code.Fritz.Errors import FritzError

_log = logging.getLogger(__name__)


class WDropdownPanel(QtWidgets.QWidget):
    """Floating panel with a coloured header and a list of selectable items.

    Positioned directly below a button; dismissed on any outside click via
    ``Qt.Popup`` semantics.

    :param parent: Widget that owns the panel (usually the ribbon button).
    :param title: Text shown in the coloured header bar.
    :param items: ``(label, callback)`` pairs — at least one required.
    :raises FritzError: When *items* is empty.
    :spec: §5.2
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        title: str,
        items: list[tuple[str, Callable[[], None]]],
    ) -> None:
        super().__init__(parent, QtCore.Qt.WindowType.Popup)
        if not items:
            raise FritzError("WDropdownPanel: items must not be empty")
        self._title = title
        self._items = list(items)
        self._checked_label: str | None = None
        self._buttons: dict[str, QtWidgets.QToolButton] = {}
        self._build_ui()

    # ── construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setObjectName("WDropdownPanel")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        header = QtWidgets.QLabel(self._title, self)
        header.setObjectName("WDropdownPanelHeader")
        header.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        vbox.addWidget(header)

        for label, callback in self._items:
            btn = QtWidgets.QToolButton(self)
            btn.setObjectName("WDropdownPanelItem")
            btn.setText(label)
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setAutoRaise(True)
            btn.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            btn.clicked.connect(
                lambda _checked=False, _cb=callback: (self.hide(), _cb())
            )
            self._buttons[label] = btn
            vbox.addWidget(btn)

        self.adjustSize()

    # ── public API ────────────────────────────────────────────────────────────

    def popup(self, button: QtWidgets.QWidget) -> None:
        """Show the panel directly below *button* in global screen coordinates.

        :param button: The ribbon button that triggered the dropdown.
        """
        pos = button.mapToGlobal(QtCore.QPoint(0, button.height()))
        self.move(pos)
        self.show()

    def set_checked(self, label: str | None) -> None:
        """Show a checkmark prefix on the row matching *label*; clear all others.

        :param label: Item label to mark, or ``None`` to clear all marks.
        """
        self._checked_label = label
        for lbl, btn in self._buttons.items():
            if lbl == label:
                btn.setText(f"✓  {lbl}")
            else:
                btn.setText(lbl)
