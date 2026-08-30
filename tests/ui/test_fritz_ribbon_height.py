"""
tests/ui/test_fritz_ribbon_height.py — WRibbon height-gap fix tests (T-RHG-01..03).

:spec: feat/ribbon-height-gap (Fritz Mode Behaviour SDD — ribbon polish)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui

_MINIMAL_SPEC = {
    "$schema_version": 1,
    "default_tab": "home",
    "missing_key_policy": "disable",
    "quick_access": [],
    "tabs": [
        {"id": "home", "label": "Home", "groups": []},
    ],
}


def _make_ribbon(qt_app):
    from Code.Fritz.WRibbon import WRibbon
    ribbon = WRibbon(spec=_MINIMAL_SPEC, dic_toolbar={})
    ribbon.show()
    return ribbon


# ---------------------------------------------------------------------------
# T-RHG-01: WRibbon has separate QAT row widget with correct objectName
# ---------------------------------------------------------------------------

def test_ribbon_has_separate_qat_row_widget(qt_app):
    """T-RHG-01: WRibbon._qat_row exists and has objectName WRibbonQATRow."""
    ribbon = _make_ribbon(qt_app)
    assert hasattr(ribbon, "_qat_row"), "T-RHG-01: _qat_row attribute must exist"
    assert ribbon._qat_row.objectName() == "WRibbonQATRow", (
        f"T-RHG-01: _qat_row objectName must be WRibbonQATRow, got {ribbon._qat_row.objectName()!r}"
    )
    # Tab row is now separate (no QAT inside it)
    assert hasattr(ribbon, "_tab_row"), "T-RHG-01: _tab_row attribute must exist"
    assert ribbon._tab_row.objectName() == "WRibbonTabRow", (
        f"T-RHG-01: _tab_row objectName must be WRibbonTabRow, got {ribbon._tab_row.objectName()!r}"
    )
    assert ribbon._qat_row is not ribbon._tab_row, (
        "T-RHG-01: _qat_row and _tab_row must be different widgets"
    )


# ---------------------------------------------------------------------------
# T-RHG-02: qatRowHeight property exists and defaults to 29
# ---------------------------------------------------------------------------

def test_qat_row_height_property_default(qt_app):
    """T-RHG-02: qatRowHeight property is readable and defaults to 29."""
    ribbon = _make_ribbon(qt_app)
    assert hasattr(ribbon, "qatRowHeight"), "T-RHG-02: qatRowHeight property must exist"
    assert ribbon.qatRowHeight == 29, (
        f"T-RHG-02: qatRowHeight default must be 29, got {ribbon.qatRowHeight}"
    )


# ---------------------------------------------------------------------------
# T-RHG-03: WRibbon total height equals qatRowHeight + tabRowHeight + 1 + contentHeight
# ---------------------------------------------------------------------------

def test_ribbon_total_height_is_sum_of_bands(qt_app):
    """T-RHG-03: WRibbon fixed height == qatRowHeight + tabRowHeight + 1 + contentHeight."""
    ribbon = _make_ribbon(qt_app)
    expected = ribbon.qatRowHeight + ribbon.tabRowHeight + 1 + ribbon.contentHeight
    actual = ribbon.height()
    assert actual == expected, (
        f"T-RHG-03: expected height {expected} "
        f"({ribbon.qatRowHeight}+{ribbon.tabRowHeight}+1+{ribbon.contentHeight}), "
        f"got {actual}"
    )
