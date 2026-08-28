"""
Delegates.py — Fritz-specific QStyledItemDelegate subclasses.

:class:`FritzEtiquetaPGN` extends the upstream ``EtiquetaPGN`` delegate to add
a left-margin NAG colour chip.  All design values (chip width, colours) arrive
through ``Code.dic_colors`` at paint time so no constants are hardcoded here.

:spec: §5.5
"""
from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

from Code.Fritz.NotationRowModel import _NAG_COLOR_KEYS
from Code.QT import Delegados

_log = logging.getLogger(__name__)

# Width in pixels of the left-margin NAG chip strip.
_CHIP_WIDTH = 4


class FritzEtiquetaPGN(Delegados.EtiquetaPGN):
    """``EtiquetaPGN`` subclass that paints a left-margin NAG colour chip.

    Inherits figurine-glyph rendering and the ChessMerida font from the
    upstream delegate.  The chip colour is read from ``Code.dic_colors``
    via the ``NAG_*`` keys added in Phase 1.

    :spec: §5.5
    """

    def __init__(self, is_white, **kwargs):
        """Initialise with ``si_fondo=True`` so background coloring is active.

        :param is_white: ``True`` for white column, ``False`` for black column,
                         ``None`` to render without figurines.
        """
        super().__init__(is_white, si_fondo=True, **kwargs)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        """Paint a left-margin chip then delegate to :class:`EtiquetaPGN`.

        The chip is only painted when the move carries a quality NAG (1-6)
        *and* the matching colour key exists in ``Code.dic_colors``.  In all
        other cases the cell renders identically to the upstream delegate.

        :spec: §5.5
        """
        import Code  # adapter boundary — late import

        data = index.model().data(index, QtCore.Qt.ItemDataRole.DisplayRole)
        chip_color: QtGui.QColor | None = None

        if isinstance(data, tuple) and len(data) >= 5:
            st_nags = data[4]
            if st_nags:
                dc = getattr(Code, "dic_colors", {})
                for nag in st_nags:
                    try:
                        nag_int = int(nag)
                    except (TypeError, ValueError):
                        continue
                    key = _NAG_COLOR_KEYS.get(nag_int)
                    if key:
                        hex_col = dc.get(key)
                        if hex_col:
                            chip_color = QtGui.QColor(hex_col)
                            break

        if chip_color is not None:
            rect = option.rect
            chip_rect = QtCore.QRect(rect.x(), rect.y(), _CHIP_WIDTH, rect.height())
            painter.save()
            painter.fillRect(chip_rect, chip_color)
            painter.restore()

            # Shift the content area right so the base delegate doesn't overdraw the chip.
            opt = QtWidgets.QStyleOptionViewItem(option)
            opt.rect = QtCore.QRect(
                rect.x() + _CHIP_WIDTH,
                rect.y(),
                max(rect.width() - _CHIP_WIDTH, 0),
                rect.height(),
            )
            super().paint(painter, opt, index)
        else:
            super().paint(painter, option, index)
