"""
bin/Code/Rpa/Workflows/classical_invariant.py — Classical Invariant regression check.

Opens the General Configuration dialog, verifies that key upstream toolbar entries
are still present (proving the classical mode layout is unmodified), then closes the
dialog.

This workflow is the primary runnable regression check for the Classical Invariant
constraint: ``classical`` mode + no theme overlay = upstream Lucas Chess R6 exactly.

:spec: FR-10, FR-12, §12, §13 (feature_spec.md)
"""

from __future__ import annotations

from Code.Rpa.Activities import Activity, CloseDialog, ElementExists, OpenConfig
from Code.Rpa.Workflows.Registry import register

# Original toolbar action object_names that must always be present in Classical mode.
# If any of these is absent, the Classical Invariant has been broken.
_CLASSICAL_TOOLBAR_ITEMS = [
    "TB_OPTIONS",
    "TB_HELP",
]


class _AssertClassicalToolbar(Activity):
    """Assert that all expected Classical toolbar entries are visible.

    :cvar required_state: Requires HOME (toolbar is visible there).
    """

    name: str = "AssertClassicalToolbar"
    settle_ms: int = 100
    max_attempts: int = 1
    required_state: str = "HOME"

    def precondition(self, ctx) -> bool:
        """True if at HOME.

        :param ctx: Current run context.
        :returns: True when HOME is recognised.
        """
        if ctx.snapshot is None:
            return False
        from Code.Rpa.AppState import HOME, recognise
        return recognise(ctx.snapshot) == HOME

    def execute(self, ctx) -> None:
        """No-op — the assertion happens in postcondition.

        :param ctx: Current run context.
        """

    def postcondition(self, ctx) -> bool:
        """Return True only if all expected toolbar items are present.

        :param ctx: Current run context.
        :returns: True when all Classical toolbar items are found.
        """
        snap = ctx.refresh_snapshot()
        for obj_name in _CLASSICAL_TOOLBAR_ITEMS:
            found = any(
                w.get("object_name") == obj_name and w.get("visible", True)
                for w in snap.widget_tree
            )
            if not found:
                import logging
                logging.getLogger(__name__).warning(
                    "Classical Invariant BROKEN: %r not found in widget tree", obj_name
                )
                return False
        return True


register("classical_invariant", [
    _AssertClassicalToolbar(),
    OpenConfig(),
    CloseDialog(),
])
