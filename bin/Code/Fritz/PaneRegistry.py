"""
bin/Code/Fritz/PaneRegistry.py — Pure sizing decisions for Fritz panes.

The registry records every ``PaneSpec`` and answers one question:
"given the current pixel height of pane *key*, what height should it be
restored to?"  All other decisions — which Qt widget to show/hide, how
to call ``setSizes`` — are the caller's responsibility.

The Qt half (the ``pane_api()`` closure dict in ``modern_fritz_ui``) calls in
here for the sizing decisions; it holds the widget references.

:spec: §5.3, Phase 3 (feature_spec.md)
:purity: pure — no Qt, no I/O, no third-party imports
"""

from __future__ import annotations

from Code.Fritz.Errors import PaneNotRegisteredError
from Code.Fritz.Types import PaneSpec


class PaneRegistry:
    """Registry of pane specifications for one Fritz window.

    :spec: §5.3
    """

    def __init__(self) -> None:
        self._specs: dict[str, PaneSpec] = {}

    # ── registration ──────────────────────────────────────────────────────────

    def register(self, spec: PaneSpec) -> None:
        """Register or replace a pane specification.

        Registering the same key twice replaces the earlier entry.  Order of
        registration determines ``names()`` order, so register in the top-to-bottom
        order you want the ribbon's Panes checkbox group to reflect.

        :param spec: The pane's identity and sizing policy.
        :spec: §5.3
        """
        if spec.key not in self._specs:
            self._specs[spec.key] = spec
        else:
            # Preserve insertion order while replacing value.
            self._specs = {
                k: (spec if k == spec.key else v)
                for k, v in self._specs.items()
            }

    # ── queries ───────────────────────────────────────────────────────────────

    def names(self) -> list[str]:
        """Return registered pane keys in registration order.

        :returns: List of pane keys.
        :spec: §5.3
        """
        return list(self._specs)

    def spec(self, key: str) -> PaneSpec:
        """Return the ``PaneSpec`` for *key*.

        :param key: Pane identifier.
        :raises PaneNotRegisteredError: If *key* has not been registered.
        :spec: §5.3
        """
        try:
            return self._specs[key]
        except KeyError as exc:
            raise PaneNotRegisteredError(key) from exc

    def restore_px(self, key: str, current_px: int) -> int:
        """Return the height to apply when re-showing pane *key*.

        Rules (in order):
        1. If *current_px* is already positive, return it unchanged — the user
           deliberately sized the pane and that preference is preserved.
        2. Otherwise return ``spec.default_px``, clamped up to ``spec.min_px``
           so a pane with a very small default still opens at a usable height.

        A pane never returns at zero height.

        :param key: Pane identifier.
        :param current_px: The pane's height as read from ``splitter.sizes()``
                           before hiding.
        :raises PaneNotRegisteredError: If *key* has not been registered.
        :spec: §5.3
        """
        s = self.spec(key)  # raises if unknown
        if current_px > 0:
            return max(current_px, s.min_px)
        return max(s.default_px, s.min_px)
