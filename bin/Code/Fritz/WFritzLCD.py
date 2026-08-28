"""
bin/Code/Fritz/WFritzLCD.py — Seven-segment LCD clock widget for Fritz mode.

Paints four digit cells and a colon separator using ``QPainterPath`` filled
rectangles.  All design values come from the ``.qss`` via the E1–E4 contract:

.. code-block:: qss

    WFritzLCD {
        qproperty-litColor: #00ff88;
        qproperty-dimColor: #103a18;
        qproperty-boxHeight: 34;
        qproperty-boxWidth: 108;
        qproperty-segmentThickness: 4;
        background-color: #000000;
        border-radius: 2px;
    }

:spec: §5.5 (WFritzLCD), §5.3 (ClockModel), FR-30
"""

from __future__ import annotations

import re

from PySide6 import QtCore, QtGui, QtWidgets

from Code.Fritz.ClockModel import digits as _clock_digits
from Code.Fritz.ClockModel import parse as _clock_parse

# ---------------------------------------------------------------------------
# Segment geometry
# ---------------------------------------------------------------------------

# Which segments are lit for each digit.
# Segments: a=top, b=top-right, c=bot-right, d=bottom, e=bot-left, f=top-left, g=middle
_SEGMENTS: dict[str, str] = {
    "0": "abcdef",
    "1": "bc",
    "2": "abdeg",
    "3": "abcdg",
    "4": "bcfg",
    "5": "acdfg",
    "6": "acdefg",
    "7": "abc",
    "8": "abcdefg",
    "9": "abcdfg",
}

_STRIP_HTML = re.compile(r"<[^>]+>")


def _make_segment_paths(
    ox: float,
    oy: float,
    dw: float,
    dh: float,
    th: float,
) -> dict[str, QtGui.QPainterPath]:
    """Return a ``QPainterPath`` for each of the 7 segments of one digit cell.

    :param ox: Left edge of the digit cell in widget coordinates.
    :param oy: Top edge of the digit cell.
    :param dw: Width of the digit cell.
    :param dh: Height of the digit cell.
    :param th: Segment thickness in pixels.
    """
    gap = max(1.0, th * 0.12)
    mid = dh * 0.5

    def hrect(rx: float, ry: float, rw: float, rh: float) -> QtGui.QPainterPath:
        p = QtGui.QPainterPath()
        p.addRect(ox + rx + gap, oy + ry + gap, max(1.0, rw - 2 * gap), max(1.0, rh - 2 * gap))
        return p

    vert_top_h = mid - th * 1.2
    vert_bot_h = mid - th * 1.2
    vert_bot_y = mid + th * 0.5

    paths: dict[str, QtGui.QPainterPath] = {
        "a": hrect(th, 0,          dw - 2 * th, th),           # top
        "b": hrect(dw - th, th,    th, vert_top_h),            # top-right
        "c": hrect(dw - th, vert_bot_y, th, vert_bot_h),      # bot-right
        "d": hrect(th, dh - th,    dw - 2 * th, th),           # bottom
        "e": hrect(0, vert_bot_y,  th, vert_bot_h),            # bot-left
        "f": hrect(0, th,          th, vert_top_h),            # top-left
        "g": hrect(th, mid - th * 0.5, dw - 2 * th, th),      # middle
    }
    return paths


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


class WFritzLCD(QtWidgets.QWidget):
    """Seven-segment LCD clock widget for Fritz mode.

    Accepts time strings in ``MM:SS``, ``H:MM:SS``, or the HTML two-line form
    emitted by ``WBase.set_clock_*``.  Painted via ``QPainterPath`` so the
    design is fully QSS-driven through the E1–E4 contract.

    :spec: §5.5 (WFritzLCD), FR-30
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self._text: str = "00:00"
        # E1 property backing store — defaults equal Modern Fritz.qss values.
        self._lit_color = QtGui.QColor("#00ff88")
        self._dim_color = QtGui.QColor("#103a18")
        self._box_height: int = 34
        self._box_width: int = 108
        self._seg_thickness: int = 4
        self.setFixedSize(self._box_width, self._box_height)

    # ------------------------------------------------------------------
    # E1 qproperty- contract
    # ------------------------------------------------------------------

    def _get_lit_color(self) -> QtGui.QColor:
        return self._lit_color

    def _set_lit_color(self, c: QtGui.QColor) -> None:
        self._lit_color = c
        self.update()

    litColor = QtCore.Property(QtGui.QColor, _get_lit_color, _set_lit_color)

    def _get_dim_color(self) -> QtGui.QColor:
        return self._dim_color

    def _set_dim_color(self, c: QtGui.QColor) -> None:
        self._dim_color = c
        self.update()

    dimColor = QtCore.Property(QtGui.QColor, _get_dim_color, _set_dim_color)

    def _get_box_height(self) -> int:
        return self._box_height

    def _set_box_height(self, v: int) -> None:
        self._box_height = v
        self.setFixedHeight(v)

    boxHeight = QtCore.Property(int, _get_box_height, _set_box_height)

    def _get_box_width(self) -> int:
        return self._box_width

    def _set_box_width(self, v: int) -> None:
        self._box_width = v
        self.setFixedWidth(v)

    boxWidth = QtCore.Property(int, _get_box_width, _set_box_width)

    def _get_seg_thickness(self) -> int:
        return self._seg_thickness

    def _set_seg_thickness(self, v: int) -> None:
        self._seg_thickness = v
        self.update()

    segmentThickness = QtCore.Property(int, _get_seg_thickness, _set_seg_thickness)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_time_text(self, text: str) -> None:
        """Update the display from a clock string.

        Accepts all forms ``ClockModel.parse`` handles, plus plain
        ``MM:SS`` / ``H:MM:SS``.  Falls back to showing the first five
        printable characters if parsing fails.

        :param text: Clock string (with or without HTML markup).
        :spec: FR-30
        """
        secs = _clock_parse(text)
        if secs is not None:
            self._text = _clock_digits(secs)
        else:
            cleaned = _STRIP_HTML.sub("", text).strip()
            self._text = cleaned[:5] if cleaned else "00:00"
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        # E2: QSS box model (background-color, border-radius) beneath our painting.
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        p = QtGui.QPainter(self)
        self.style().drawPrimitive(
            QtWidgets.QStyle.PrimitiveElement.PE_Widget, opt, p, self
        )

        w = self.width()
        h = self.height()
        text = self._text  # "MM:SS" guaranteed by set_time_text / __init__

        # Layout: 4 digit cells + 1 colon slot.
        # Colon slot is narrower than a digit (ratio below).
        pad_x = max(3.0, w * 0.04)
        pad_y = max(2.0, h * 0.10)
        usable_w = w - 2 * pad_x
        usable_h = h - 2 * pad_y

        colon_ratio = 0.30
        # 4 digits + colon_ratio = total units across usable_w
        digit_w = usable_w / (4 + colon_ratio)
        colon_w = digit_w * colon_ratio
        digit_h = usable_h
        th = max(2.0, self._seg_thickness * (digit_h / 34.0))

        # X positions for each cell: d0 d1 [:] d2 d3
        cell_x = [
            pad_x,
            pad_x + digit_w,
            pad_x + 2 * digit_w,               # colon
            pad_x + 2 * digit_w + colon_w,
            pad_x + 3 * digit_w + colon_w,
        ]

        chars = list(text)
        cells = (
            [chars[0], chars[1], ":", chars[3], chars[4]]
            if len(chars) == 5 and chars[2] == ":"
            else list("00:00")
        )

        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(QtCore.Qt.PenStyle.NoPen)

        for i, ch in enumerate(cells):
            cx = cell_x[i]
            cy = pad_y
            if ch == ":":
                dot_r = max(2.0, th * 0.55)
                dot_x = cx + (colon_w - dot_r) / 2
                dot_y1 = cy + digit_h * 0.28
                dot_y2 = cy + digit_h * 0.62
                p.setBrush(QtGui.QBrush(self._lit_color))
                p.drawEllipse(QtCore.QRectF(dot_x, dot_y1, dot_r, dot_r))
                p.drawEllipse(QtCore.QRectF(dot_x, dot_y2, dot_r, dot_r))
            else:
                seg_on = _SEGMENTS.get(ch, "")
                paths = _make_segment_paths(cx, cy, digit_w, digit_h, th)
                for seg, path in paths.items():
                    color = self._lit_color if seg in seg_on else self._dim_color
                    p.fillPath(path, QtGui.QBrush(color))

        p.end()
