"""
tests/unit/fritz/test_board_fit.py — Pure unit tests for ``Code.Fritz.BoardFit`` (T-BFIT-01..08).

xfail stubs until Phase 2 (feat/fritz-fixed-window).

:spec: §5.3, Phase 2 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_PHASE2 = "Requires Phase 2 (feat/fritz-fixed-window)"


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_ancho_for_width_piece_matches_characterisation_table():
    """T-BFIT-01: ancho_for_width_piece matches the harvested characterisation table."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_width_piece_for_ancho_is_monotonic():
    """T-BFIT-02: width_piece_for_ancho is monotonic and never returns an ancho above its target."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_round_trip_is_identity():
    """T-BFIT-03: width_piece_for_ancho(ancho_for_width_piece(ap)) == ap for all ap in range."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_fit_clamps_to_min_ancho_on_zero_pane():
    """T-BFIT-04: fit clamps to MIN_ANCHO when overhead exceeds the pane."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_fit_is_idempotent():
    """T-BFIT-05: fit is idempotent — feeding back its output returns the same ap."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_negative_pane_returns_min_ap():
    """T-BFIT-06: a negative or zero pane size returns MIN_AP rather than raising."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_tam_frontera_shifts_ancho_by_double():
    """T-BFIT-07: tam_frontera variations shift ancho by exactly 2 * tam_frontera."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_fit_result_clamped_flag():
    """T-BFIT-08: FitResult.clamped is True exactly when MIN_ANCHO floor was hit."""
    pytest.fail("not yet implemented")
