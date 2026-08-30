"""
bin/Code/Rpa/Types.py — Dependency-free frozen dataclasses shared across the RPA layer.

**ZERO third-party imports** — enforced by ``test_types_module_has_no_third_party_imports``.
Every pure RPA module imports from here, so a third-party import in this file would drag
that dependency into a plain app start. (N-RPA-1)

CV-specific types (``Screenshot``, ``Match``) live in ``Vision/Capture.py`` and
``Vision/Template.py`` respectively because they depend on ``cv2``/``numpy`` (D10).

:spec: NFR-1 (N-RPA-1), §4
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class Rect:
    """Axis-aligned bounding rectangle in **logical (DPR-1) pixel coordinates**.

    All coordinate arithmetic in the RPA layer uses logical pixels. ``Screenshot``
    normalises device pixels to logical before returning; anchors, distance checks, and
    all tier comparisons run on ``Rect`` values from this class.

    :param x: Left edge (inclusive), logical pixels.
    :param y: Top edge (inclusive), logical pixels.
    :param w: Width in logical pixels.
    :param h: Height in logical pixels.
    """

    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        """Right edge (exclusive), logical pixels.

        :return: x + w
        """
        return self.x + self.w

    @property
    def bottom(self) -> int:
        """Bottom edge (exclusive), logical pixels.

        :return: y + h
        """
        return self.y + self.h

    @property
    def cx(self) -> int:
        """Horizontal centre, logical pixels.

        :return: x + w // 2
        """
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        """Vertical centre, logical pixels.

        :return: y + h // 2
        """
        return self.y + self.h // 2

    def contains(self, other: Rect) -> bool:
        """Return True if *other* is fully contained within this rect.

        :param other: The rect to test for containment.
        :return: True when other lies entirely inside self.
        """
        return (
            self.x <= other.x
            and self.y <= other.y
            and other.right <= self.right
            and other.bottom <= self.bottom
        )

    def iou(self, other: Rect) -> float:
        """Intersection over Union with *other*.

        Returns 0.0 when the rects do not overlap.

        :param other: The rect to compute IoU against.
        :return: IoU value in [0.0, 1.0].
        """
        ix = max(0, min(self.right, other.right) - max(self.x, other.x))
        iy = max(0, min(self.bottom, other.bottom) - max(self.y, other.y))
        inter = ix * iy
        if inter == 0:
            return 0.0
        union = self.w * self.h + other.w * other.h - inter
        return inter / union if union > 0 else 0.0

    def intersects(self, other: Rect) -> bool:
        """Return True if this rect overlaps *other* (touching edges count).

        :param other: The rect to test against.
        :return: True when the rects share at least one pixel column and row.
        """
        return (
            self.x < other.right
            and other.x < self.right
            and self.y < other.bottom
            and other.y < self.bottom
        )

    def intersection(self, other: Rect) -> Rect | None:
        """Return the overlapping sub-rect, or ``None`` when they do not overlap.

        :param other: The rect to intersect with.
        :return: Intersection rect, or None.
        """
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        r = min(self.right, other.right)
        b = min(self.bottom, other.bottom)
        if r <= x or b <= y:
            return None
        return Rect(x, y, r - x, b - y)

    @property
    def area(self) -> int:
        """Area in square logical pixels.

        :return: w * h
        """
        return self.w * self.h

    def translate(self, dx: int, dy: int) -> Rect:
        """Return a copy shifted by (*dx*, *dy*).

        :param dx: Horizontal offset.
        :param dy: Vertical offset.
        :return: Translated rect.
        """
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def inset(self, px: int) -> Rect:
        """Return a copy shrunk by *px* on every side.

        Clamps to zero size so the result is always valid.

        :param px: Pixels to remove from each edge.
        :return: Inset rect.
        """
        w = max(0, self.w - 2 * px)
        h = max(0, self.h - 2 * px)
        return Rect(self.x + px, self.y + px, w, h)

    def contains_point(self, px: int, py: int) -> bool:
        """Return True if (*px*, *py*) lies inside this rect.

        :param px: X coordinate.
        :param py: Y coordinate.
        :return: True when the point is inside (edges are inclusive).
        """
        return self.x <= px < self.right and self.y <= py < self.bottom


@dataclass(frozen=True)
class ElementRef:
    """A resolved reference to a UI element — the selector that found it, plus its rect.

    ``ElementRef`` carries the selector string rather than a Qt pointer, matching
    UiPath's model where selectors re-evaluate per activity.  This structurally
    eliminates the use-after-free class that Qt pointers in long-lived test objects
    cause.  ``QtDriver`` re-resolves the selector at actuation time and validates with
    ``shiboken6.isValid``.

    :param selector: The compact-string selector used to find this element.
    :param rect: Bounding rect in logical (DPR-1) pixels.
    """

    selector: str
    rect: Rect


@dataclass(frozen=True)
class Snapshot:
    """A point-in-time read of the app: state name, widget tree, and timestamp.

    Created by ``Driver.snapshot()`` at the start of each pump. Pure modules (the
    runner, recogniser, resolver) read from a ``Snapshot`` — they never call Qt
    directly.

    :param state_name: The recognised app state at snapshot time (one of the 8
        constants in ``AppState``), or ``"UNKNOWN"`` if unrecognised.
    :param widget_tree: List of widget-info dicts as returned by the driver.
        Each dict has at minimum ``cls``, ``object_name``, ``text``, ``visible``,
        ``rect`` keys (see ``Driver.snapshot`` contract).
    :param timestamp_ms: Wall-clock time in milliseconds when the snapshot was taken,
        as returned by ``driver.now()``.
    :param screenshot: Optional :class:`~Code.Rpa.Vision.Capture.Screenshot` taken
        at snapshot time by ``QtDriver``.  Typed ``Any`` so that ``Types.py`` remains
        free of numpy/cv2 imports (N-RPA-1).  ``None`` in unit-test snapshots and
        whenever the image/OCR tiers are not required.
    """

    state_name: str
    widget_tree: list[dict[str, Any]]
    timestamp_ms: float
    screenshot: Any = None


@dataclass(frozen=True)
class SubRect:
    """A painted sub-element of a composite widget (e.g. a tab inside a QTabBar).

    ``QtDriver.widget_info`` emits these when a widget class has known sub-element
    geometry (``QTabBar`` → per-tab rects; ``QToolBar``/``QMenuBar`` → per-action rects).
    Sub-rects are parent-relative logical pixels, exactly like ``w.geometry()``; callers
    must add the parent's capture-absolute origin before hit-testing.

    :param index: Zero-based position within the composite widget.
    :param role: Element role: ``"tab"`` | ``"action"`` | ``"item"``.
    :param rect: Parent-relative bounding rect in logical pixels.
    :param text: Label text, or empty string when not applicable.
    :param selected: True when this sub-element is the currently selected/checked one.
    """

    index: int
    role: str
    rect: Rect
    text: str = ""
    selected: bool = False
