"""
tests/unit/rpa/test_style_source.py — unit tests for Vision/StyleSource.py.

The go/no-go test is test_style_source_caissa_qss_214_loaded_unmatched:
if it fails, the bridge has reproduced the mistake of pointing at dead code.

:spec: docs/features/rpa-design-vision/feature_spec.md N-RPAV-5
"""
import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires Phase 2c — StyleSource.py not yet written")
def test_style_source_wribbon_file_fill_governed_by_paintEvent():
    """style_sources_for WRibbonTabBar File tab must return WRibbon.py:118 (_BG_FIRST)
    as the effective source for fill colour, not either QSS file."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2c — StyleSource.py not yet written")
def test_style_source_fritz_widgets_qss_290_matched_overridden():
    """fritz-widgets.qss:290 ::tab:first background-color must return
    effective='matched_overridden' — a widget matches but paintEvent wins."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2c — StyleSource.py not yet written")
def test_style_source_caissa_qss_214_loaded_unmatched():
    """Caissa.qss:214 QTabWidget::pane must return effective='loaded_unmatched'.
    No QTabWidget exists in the application. This is the go/no-go test: if it
    returns 'effective', the bridge has reproduced the original mistake."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2c — StyleSource.py not yet written")
def test_style_source_font_mismatch_detected():
    """StyleSource must detect when QSS font-size (8pt from fritz-widgets.qss:285)
    differs from the widget's self.font() (10pt from WRibbon.py:703)."""
    raise NotImplementedError
