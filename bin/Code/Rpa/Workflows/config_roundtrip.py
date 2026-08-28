"""
bin/Code/Rpa/Workflows/config_roundtrip.py — Configuration dialog roundtrip test.

Opens the General Configuration dialog, changes the player name, closes (saving),
reopens the dialog, and verifies the new name persisted.  This exercises the
full write-read roundtrip of the config form.

:spec: FR-10, §13 (feature_spec.md)
"""

from __future__ import annotations

import uuid

from Code.Rpa.Activities import Activity, CloseDialog, OpenConfig, TypeInto
from Code.Rpa.Workflows.Registry import register

# Unique sentinel suffix so the roundtrip test is deterministic across runs
_TEST_NAME_PREFIX = "rpa_test_"

# Selector for the player name field in the Configuration dialog
_PLAYER_NAME_SELECTOR = '{"cls": "QLineEdit", "object_name": "player_name"}'


class _SetPlayerName(Activity):
    """Set the player name field to a test value.

    :cvar required_state: Requires the Config dialog to be open (DIALOG_CONFIG).
    """

    name: str = "SetPlayerName"
    settle_ms: int = 200
    max_attempts: int = 2

    def __init__(self, test_name: str) -> None:
        """Initialise with the target player name.

        :param test_name: Value to set in the player name field.
        """
        super().__init__()
        self._test_name = test_name

    def precondition(self, ctx) -> bool:
        """True if the Config dialog is open.

        :param ctx: Current run context.
        :returns: True when DIALOG_CONFIG is recognised.
        """
        if ctx.snapshot is None:
            return False
        from Code.Rpa.AppState import DIALOG_CONFIG, recognise
        return recognise(ctx.snapshot) == DIALOG_CONFIG

    def execute(self, ctx) -> None:
        """Type the test name into the player name field.

        :param ctx: Current run context.
        """
        ctx.driver.set_text(_PLAYER_NAME_SELECTOR, self._test_name)

    def postcondition(self, ctx) -> bool:
        """Verify the field now shows the test name.

        :param ctx: Current run context.
        :returns: True when the player name field contains the expected value.
        """
        snap = ctx.refresh_snapshot()
        for w in snap.widget_tree:
            if w.get("object_name") == "player_name":
                return self._test_name in (w.get("text") or "")
        return False


class _AcceptDialog(Activity):
    """Accept the Config dialog (OK / Accept button).

    :cvar required_state: Requires DIALOG_CONFIG.
    """

    name: str = "AcceptDialog"
    settle_ms: int = 300
    max_attempts: int = 2

    def precondition(self, ctx) -> bool:
        """True if the Config dialog is open.

        :param ctx: Current run context.
        :returns: True when DIALOG_CONFIG is recognised.
        """
        if ctx.snapshot is None:
            return False
        from Code.Rpa.AppState import DIALOG_CONFIG, recognise
        return recognise(ctx.snapshot) == DIALOG_CONFIG

    def execute(self, ctx) -> None:
        """Click the Accept/OK button.

        :param ctx: Current run context.
        """
        ctx.driver.click_dialog_button(accept=True)

    def postcondition(self, ctx) -> bool:
        """True once the dialog is gone.

        :param ctx: Current run context.
        :returns: True when no longer at DIALOG_CONFIG.
        """
        snap = ctx.refresh_snapshot()
        from Code.Rpa.AppState import DIALOG_CONFIG, recognise
        return recognise(snap) != DIALOG_CONFIG


class _VerifyPlayerName(Activity):
    """Reopen Config and verify the player name was persisted.

    :cvar required_state: Requires HOME so we can open Config again.
    """

    name: str = "VerifyPlayerName"
    settle_ms: int = 300
    max_attempts: int = 2
    required_state: str = "HOME"

    def __init__(self, expected_name: str) -> None:
        """Initialise with the expected player name.

        :param expected_name: The value that should be in the player name field.
        """
        super().__init__()
        self._expected_name = expected_name

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
        """Open the Config dialog.

        :param ctx: Current run context.
        """
        ctx.driver.trigger_action("Options")

    def postcondition(self, ctx) -> bool:
        """Verify the player name field shows the expected value.

        :param ctx: Current run context.
        :returns: True when the name persisted correctly.
        """
        snap = ctx.refresh_snapshot()
        from Code.Rpa.AppState import DIALOG_CONFIG, recognise
        if recognise(snap) != DIALOG_CONFIG:
            return False
        for w in snap.widget_tree:
            if w.get("object_name") == "player_name":
                return self._expected_name in (w.get("text") or "")
        return False


def _build_config_roundtrip() -> list:
    """Build a fresh config-roundtrip activity list with a unique test name.

    Using a factory rather than a module-level list so each ``rpa_run``
    gets a distinct test name, making repeated runs independently verifiable.

    :returns: List of :class:`~Code.Rpa.Activities.Activity` instances.
    """
    test_name = _TEST_NAME_PREFIX + uuid.uuid4().hex[:8]
    return [
        OpenConfig(),
        _SetPlayerName(test_name),
        _AcceptDialog(),
        _VerifyPlayerName(test_name),
        CloseDialog(),
    ]


register("config_roundtrip", _build_config_roundtrip())
