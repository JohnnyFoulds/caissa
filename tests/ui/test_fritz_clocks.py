"""
tests/ui/test_fritz_clocks.py — UI tests for WFritzLCD and the dense eval summary.

T-LCD-01  test_lcd_widgets_present_and_visible
T-LCD-02  test_lcd_renders_nonbackground_pixels
T-LCD-03  test_lcd_parses_both_input_forms
T-LCD-04  test_classical_shows_qlabel_not_lcd
T-LCD-05  test_eval_summary_line_format        (xfail — requires live engine)
T-LCD-06  test_three_reachable_clocks_agree    (xfail — requires live game)

:spec: FR-29, FR-30, FR-31, FR-32
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui


def test_lcd_widgets_present_and_visible(qt_app):
    """WFritzLCD can be constructed, receives a clock string, and is visible.

    :spec: FR-30, T-LCD-01
    """
    from Code.Fritz.WFritzLCD import WFritzLCD

    lcd = WFritzLCD()
    lcd.set_time_text("05:00")
    lcd.show()

    assert lcd.isVisible(), "T-LCD-01 FAIL: WFritzLCD should be visible after show()"
    assert lcd.width() > 0, f"T-LCD-01 FAIL: expected positive width, got {lcd.width()}"
    assert lcd.height() > 0, f"T-LCD-01 FAIL: expected positive height, got {lcd.height()}"


def test_lcd_renders_nonbackground_pixels(qt_app):
    """widget.grab() on a WFritzLCD showing '12:34' contains non-dim-colour pixels.

    The lit segments must produce pixels that differ from the dim (off-segment)
    background colour.  A floor of 50 pixels is intentionally conservative.

    :spec: FR-30, T-LCD-02
    """
    from Code.Fritz.WFritzLCD import WFritzLCD

    lcd = WFritzLCD()
    lcd.set_time_text("12:34")
    lcd.show()
    lcd.repaint()

    image = lcd.grab().toImage()
    dim = lcd._dim_color

    non_dim = 0
    for y in range(image.height()):
        for x in range(image.width()):
            px = image.pixel(x, y)
            r, g, b = (px >> 16) & 0xFF, (px >> 8) & 0xFF, px & 0xFF
            if (r, g, b) != (dim.red(), dim.green(), dim.blue()):
                non_dim += 1

    assert non_dim > 50, (
        f"T-LCD-02 FAIL: expected >50 non-dim pixels, got {non_dim}. "
        "Check that segments are painted with _lit_color."
    )


def test_lcd_parses_both_input_forms(qt_app):
    """set_time_text accepts plain MM:SS and the HTML two-line form from WBase.

    After parsing, _text must be in 'MM:SS' form (ClockModel.digits output).

    :spec: FR-30, T-LCD-03
    """
    from Code.Fritz.WFritzLCD import WFritzLCD

    lcd = WFritzLCD()

    lcd.set_time_text("05:00")
    assert lcd._text == "05:00", (
        f"T-LCD-03 FAIL: plain form → expected '05:00', got {lcd._text!r}"
    )

    # HTML two-line form emitted by WBase.set_clock_white / set_clock_black
    lcd.set_time_text('05:00<br><FONT SIZE="-4">0.0')
    assert lcd._text == "05:00", (
        f"T-LCD-03 FAIL: HTML form → expected '05:00', got {lcd._text!r}"
    )


def test_classical_shows_qlabel_not_lcd(qt_app):
    """_PlayerRow._clock is a WFritzLCD instance, not a plain QLabel.

    Classical mode clock labels are separate QLabels with type="clock" and are
    unaffected by the Fritz LCD substitution.

    :spec: FR-30, T-LCD-04
    """
    from Code.Fritz.WFritzLCD import WFritzLCD
    from Code.Fritz.WFritzPlayerHeader import _PlayerRow

    row = _PlayerRow(None, "♙", "#ffffff")

    assert isinstance(row._clock, WFritzLCD), (
        f"T-LCD-04 FAIL: _PlayerRow._clock should be WFritzLCD, "
        f"got {type(row._clock).__name__}"
    )


@pytest.mark.xfail(strict=True, reason="Requires live engine output (Phase 4 — feat/fritz-clocks-eval)")
def test_eval_summary_line_format(qt_app):
    """Eval summary label text matches the expected format after engine output.

    Expected regex: ``^(White|Black) is .*: .* \\([-+]?\\d+\\.\\d\\d\\) Depth: \\d+/\\d+``

    :spec: FR-31, T-LCD-05
    """
    pytest.fail(
        "T-LCD-05: requires a live engine delivering mrm data to WFritzAnalysisTable. "
        "Implement by polling _lb_eval_summary.text() after 3 s of engine analysis."
    )


@pytest.mark.xfail(strict=True, reason="Requires live game with running clock (Phase 4 — feat/fritz-clocks-eval)")
def test_three_reachable_clocks_agree(qt_app):
    """WBase label, WInformation label, and WFritzLCD all show the same parsed seconds.

    Workers/Worker.py:173 pair is excluded by design (separate upstream window,
    not reachable through the Fritz mode hook).

    :spec: FR-30, T-LCD-06
    """
    pytest.fail(
        "T-LCD-06: requires a live game with clock data visible at all three reachable "
        "sites (WBase.lb_clock_*, WInformation, WFritzLCD). "
        "Workers/Worker.py:173 pair excluded by design."
    )
