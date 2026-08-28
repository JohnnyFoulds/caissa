"""
bin/Code/Fritz/Types.py — Dependency-free frozen dataclasses shared across the Fritz layer.

**ZERO third-party imports** — enforced by ``test_types_module_has_no_third_party_imports``.
Every pure Fritz module imports from here. Reuses ``Rpa.Types.Rect`` for geometry rather
than declaring a second bounding-rectangle type.

:spec: §4, §5.1 (feature_spec.md), NFR-1 (N-FRITZ-1)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaneSpec:
    """Specification for a single Fritz pane.

    :param key: Machine-readable identifier used by ``PaneRegistry`` and the ribbon.
    :param label: Human-readable pane name shown in the title bar and Panes group.
    :param default_px: Default height in logical pixels when the pane is first shown.
    :param min_px: Minimum height; ``PaneRegistry.restore_px`` never returns below this.

    :spec: §5.1
    """

    key: str
    label: str
    default_px: int
    min_px: int


@dataclass(frozen=True, slots=True)
class RibbonSlot:
    """A single slot (button) in the ribbon content map.

    :param key: Action key — a ``TB_*`` constant or ``caissa:<name>`` namespaced key.
    :param size: Display size: ``"large"`` (full-height) or ``"small"`` (half-height).
    :param label: Override label; ``None`` means inherit from the ``QAction`` text.
    :param tab_id: Containing tab identifier (e.g. ``"home"``).
    :param group_id: Containing group identifier (e.g. ``"home.game"``).

    :spec: §5.1
    """

    key: str
    size: str
    label: str | None
    tab_id: str
    group_id: str


@dataclass(frozen=True, slots=True)
class EvalSummary:
    """Parsed evaluation from the engine's ``mrm``.

    :param text: Verbal assessment, e.g. ``"Black is slightly better"``.
    :param nag: NAG number (0 = equal, 13 = unclear, etc.) or ``None`` if unknown.
    :param cp: Centipawn score from White's perspective, or ``None`` for mate scores.
    :param depth: Search depth reached.
    :param seldepth: Selective search depth.
    :param nodes: Nodes searched.
    :param ms: Time elapsed in milliseconds.

    :spec: §5.1
    """

    text: str
    nag: int | None
    cp: int | None
    depth: int
    seldepth: int
    nodes: int
    ms: int


@dataclass(frozen=True, slots=True)
class FitResult:
    """Result of a board-fit calculation.

    :param width_piece: Computed piece size in logical pixels.
    :param ancho: Resulting board side length (``width_square * 8 + margins``).
    :param clamped: ``True`` when the ``MIN_ANCHO`` floor was hit; the caller may log this.

    :spec: §5.1
    """

    width_piece: int
    ancho: int
    clamped: bool
