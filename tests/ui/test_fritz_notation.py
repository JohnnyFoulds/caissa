"""
tests/ui/test_fritz_notation.py — Fritz notation tab strip and NAG palette tests.

xfail stubs until Phase 5 (feat/fritz-notation).

:spec: Phase 5 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.rpa_ui

_PHASE5 = "Requires Phase 5 (feat/fritz-notation)"


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_tab_labels_in_order():
    """T-NOT-01: Notation tab strip has the six expected labels in order."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_tab_switch_no_error():
    """T-NOT-02: Switching to 'Score sheet' tab raises no error."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_current_move_highlighted():
    """T-NOT-03: The selected move is visually highlighted in the notation grid."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_nag_rows_present_with_correct_count():
    """T-NOT-04: Both NAG rows are present with the correct button count."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_nag_button_applies_to_move():
    """T-NOT-05: Clicking '!' sets NAG 1 on the current move per game_info."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_fritz_delegate_attached_in_fritz():
    """T-NOT-06: Notation column delegate is FritzEtiquetaPGN in Fritz and plain EtiquetaPGN in classical."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_nag_annotated_cell_differs_from_unannotated():
    """T-NOT-07: A NAG-annotated move cell renders differently from an unannotated one."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_classical_has_no_tab_strip():
    """T-NOT-08: Classical mode has no notation tab strip."""
    pytest.fail("not yet implemented")
