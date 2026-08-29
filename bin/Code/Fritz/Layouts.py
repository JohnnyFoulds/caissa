"""
bin/Code/Fritz/Layouts.py — Named layout presets for Fritz mode splitters.

Each preset specifies proportional splitter sizes (integer weights; Qt scales them to
the available space automatically) for the main horizontal splitter and the
right-column vertical splitter.

Right-column slot order (modern_fritz_ui.py _build_fritz_right_col):
    [0] WFritzPlayerHeader  — players / clocks
    [1] WFritzAnalysisTable — engine lines
    [2] WFritzEvalGraph     — eval profile
    [3] WBase.pgn           — notation / move list

Preset names mirror the Fritz 18 manual §000078 where possible.

:spec: Phase 5 (feature_spec.md fritz-mode)
:tier: pure — only stdlib, no PySide6, no upstream Code.* imports
"""

from __future__ import annotations

from typing import Final

# ── Named presets ───────────────────────────────────────────────────────────
# Integer weight lists; passed to QSplitter.setSizes() — Qt normalises to pixels.

PRESETS: Final[dict[str, dict[str, list[int]]]] = {
    "Standard": {
        "main":      [600, 400],
        "right_col": [90,  430, 120, 360],
    },
    "Big Board": {
        "main":      [750, 250],
        "right_col": [90,  370, 100, 340],
    },
    "Big Notation": {
        "main":      [500, 500],
        "right_col": [70,  300, 100, 530],
    },
    "Big Engine": {
        "main":      [450, 550],
        "right_col": [70,  600, 100, 230],
    },
    "Board Only": {
        "main":      [870, 130],
        "right_col": [60,  200,  80, 160],
    },
    "All Windows": {
        "main":      [400, 600],
        "right_col": [90,  330, 130, 450],
    },
}

_FACTORY: Final[str] = "Standard"


def preset_names() -> list[str]:
    """Return the ordered list of preset names."""
    return list(PRESETS)


def factory_name() -> str:
    """Return the name of the factory-default preset."""
    return _FACTORY


def apply_preset(name: str, main_splitter, right_col_splitter) -> None:
    """Apply a named layout preset to the two splitters.

    Falls back to ``"Standard"`` if *name* is not found.

    :param name: Preset name from :data:`PRESETS`.
    :param main_splitter: Main horizontal ``QSplitter``.
    :param right_col_splitter: Right-column vertical ``QSplitter``.
    """
    p = PRESETS.get(name, PRESETS[_FACTORY])
    main_splitter.setSizes(p["main"])
    right_col_splitter.setSizes(p["right_col"])
