"""
tests/unit/amiga/test_activities.py — Unit tests for bin/Code/Amiga/Activities.py.

All tests use a FakeDriver that replays pre-built PIL images.  No FS-UAE
process is required.  The FakeDriver pattern follows the DOSBox equivalent in
tests/unit/ and docs/rpa/new-target-guide.md.

:purity: unit
"""

from __future__ import annotations

import io
from typing import Any

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — FakeDriver and image factories
# ---------------------------------------------------------------------------

def _solid_rgb_image(r: int, g: int, b: int, w: int = 640, h: int = 400):
    """Return a PIL Image filled with a solid colour.

    :param r: Red channel value (0–255).
    :param g: Green channel value (0–255).
    :param b: Blue channel value (0–255).
    :param w: Image width in pixels.
    :param h: Image height in pixels.
    :returns: PIL ``Image`` object.
    """
    from PIL import Image
    return Image.new("RGB", (w, h), (r, g, b))


def _black_image() -> Any:
    """Solid black image — represents a blank/uninitialised window."""
    return _solid_rgb_image(0, 0, 0)


def _bright_image() -> Any:
    """Solid mid-grey image — represents a window with visible content."""
    return _solid_rgb_image(128, 100, 80)


def _diff_image(base, square_x: int, square_y: int, half_w: int = 20, half_h: int = 20) -> Any:
    """Return a copy of *base* with one square region brightened."""
    from PIL import Image
    img = base.copy()
    region = Image.new("RGB", (half_w * 2, half_h * 2), (220, 200, 180))
    img.paste(region, (square_x - half_w, square_y - half_h))
    return img


class FakeDriver:
    """Minimal driver stub that returns images from a pre-loaded queue.

    :param images: Sequence of PIL images returned in order on successive
        ``screenshot()`` calls.  When the queue is exhausted, the last image
        is returned repeatedly.
    """

    def __init__(self, images: list) -> None:
        self._images = list(images)
        self._idx = 0
        self.clicks: list[tuple[int, int]] = []
        self.keys: list = []

    def screenshot(self):
        img = self._images[min(self._idx, len(self._images) - 1)]
        self._idx += 1
        return img

    def screenshot_to(self, path) -> None:
        pass

    def focus(self) -> None:
        pass

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

    def double_click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

    def key(self, key_name: str) -> None:
        self.keys.append(key_name)

    def key_code(self, keycode: int) -> None:
        self.keys.append(keycode)

    def mousedown(self, x: int, y: int) -> None:
        pass

    def mouseup(self, x: int, y: int) -> None:
        pass


class FakeProcess:
    """Minimal FsUaeProcess stub.

    :param running: Initial is_running state.
    """

    def __init__(self, running: bool = True) -> None:
        self.is_running = running
        self.launched = False

    def launch(self) -> None:
        self.is_running = True
        self.launched = True


# ---------------------------------------------------------------------------
# EnsureFsUaeRunning
# ---------------------------------------------------------------------------

class TestEnsureFsUaeRunning:
    def test_precondition_always_true(self):
        """precondition returns True regardless of screenshot or ctx."""
        from Code.Amiga.Activities import EnsureFsUaeRunning
        process = FakeProcess(running=True)
        act = EnsureFsUaeRunning(process)
        assert act.precondition(None, {}) is True
        assert act.precondition(_black_image(), {}) is True

    def test_execute_noop_when_already_running(self):
        """execute() does not call launch() when process is already running."""
        from Code.Amiga.Activities import EnsureFsUaeRunning
        process = FakeProcess(running=True)
        act = EnsureFsUaeRunning(process)
        driver = FakeDriver([_bright_image()])
        act.execute(driver, {})
        assert not process.launched

    def test_execute_launches_when_not_running(self):
        """execute() calls process.launch() when not running."""
        from Code.Amiga.Activities import EnsureFsUaeRunning
        process = FakeProcess(running=False)
        act = EnsureFsUaeRunning(process)
        driver = FakeDriver([_bright_image()])
        act.execute(driver, {})
        assert process.launched

    def test_postcondition_true_when_running(self):
        """postcondition returns True when process.is_running is True."""
        from Code.Amiga.Activities import EnsureFsUaeRunning
        process = FakeProcess(running=True)
        act = EnsureFsUaeRunning(process)
        assert act.postcondition(None, {}) is True

    def test_postcondition_false_when_not_running(self):
        """postcondition returns False when process.is_running is False."""
        from Code.Amiga.Activities import EnsureFsUaeRunning
        process = FakeProcess(running=False)
        act = EnsureFsUaeRunning(process)
        assert act.postcondition(None, {}) is False


# ---------------------------------------------------------------------------
# LaunchBattleChessFromWorkbench
# ---------------------------------------------------------------------------

class TestLaunchBattleChessFromWorkbench:
    def test_precondition_true_on_workbench_image(self):
        """precondition True when Workbench content is visible (brightness > 4)."""
        from Code.Amiga.Activities import LaunchBattleChessFromWorkbench
        act = LaunchBattleChessFromWorkbench()
        assert act.precondition(_workbench_image(), {}) is True

    def test_precondition_false_on_black_image(self):
        """precondition False when screen is still blank."""
        from Code.Amiga.Activities import LaunchBattleChessFromWorkbench
        act = LaunchBattleChessFromWorkbench()
        assert act.precondition(_black_image(), {}) is False

    def test_execute_double_clicks_disk_then_executable(self):
        """execute() makes two double_clicks: disk icon first, then executable."""
        from Code.Amiga.Activities import LaunchBattleChessFromWorkbench
        import unittest.mock as mock
        act = LaunchBattleChessFromWorkbench()
        double_clicks = []

        class _Drv(FakeDriver):
            def double_click(self, x, y):
                double_clicks.append((x, y))

        driver = _Drv([_workbench_image()] * 5)
        with mock.patch("Code.Amiga.Activities.time.sleep"):
            act.execute(driver, {})
        assert len(double_clicks) == 2
        assert double_clicks[0] == (LaunchBattleChessFromWorkbench._DISK_ICON_X,
                                    LaunchBattleChessFromWorkbench._DISK_ICON_Y)
        assert double_clicks[1] == (LaunchBattleChessFromWorkbench._EXEC_ICON_X,
                                    LaunchBattleChessFromWorkbench._EXEC_ICON_Y)

    def test_postcondition_true_on_title_screen(self):
        """postcondition True once game title screen loads (brightness > 15)."""
        from Code.Amiga.Activities import LaunchBattleChessFromWorkbench
        act = LaunchBattleChessFromWorkbench()
        assert act.postcondition(_solid_rgb_image(50, 30, 20), {}) is True  # mean ~33

    def test_postcondition_false_on_workbench_image(self):
        """postcondition False while still on Workbench (mean brightness 8, below 15)."""
        from Code.Amiga.Activities import LaunchBattleChessFromWorkbench
        act = LaunchBattleChessFromWorkbench()
        assert act.postcondition(_workbench_image(), {}) is False

    def test_postcondition_false_on_black_loading_screen(self):
        """postcondition False during black loading phase (brightness ~3)."""
        from Code.Amiga.Activities import LaunchBattleChessFromWorkbench
        act = LaunchBattleChessFromWorkbench()
        assert act.postcondition(_black_image(), {}) is False


# ---------------------------------------------------------------------------
# WaitForTitle
# ---------------------------------------------------------------------------

class TestWaitForTitle:
    def test_precondition_always_true(self):
        """precondition is unconditional."""
        from Code.Amiga.Activities import WaitForTitle
        act = WaitForTitle()
        assert act.precondition(None, {}) is True
        assert act.precondition(_black_image(), {}) is True

    def test_execute_is_noop(self):
        """execute() performs no driver calls."""
        from Code.Amiga.Activities import WaitForTitle
        driver = FakeDriver([_bright_image()])
        act = WaitForTitle()
        act.execute(driver, {})
        assert driver.clicks == []
        assert driver.keys == []

    def test_postcondition_true_on_bright_image(self):
        """postcondition True for a non-black (content-bearing) image."""
        from Code.Amiga.Activities import WaitForTitle
        act = WaitForTitle()
        assert act.postcondition(_bright_image(), {}) is True

    def test_postcondition_false_on_black_image(self):
        """postcondition False for a blank (all-black) screen."""
        from Code.Amiga.Activities import WaitForTitle
        act = WaitForTitle()
        assert act.postcondition(_black_image(), {}) is False

    def test_postcondition_false_on_none(self):
        """postcondition False when no screenshot provided."""
        from Code.Amiga.Activities import WaitForTitle
        act = WaitForTitle()
        assert act.postcondition(None, {}) is False

    def test_postcondition_true_on_workbench_image(self):
        """postcondition True on dark Workbench screen (mean ~8, above 4.0 threshold)."""
        from Code.Amiga.Activities import WaitForTitle
        act = WaitForTitle()
        assert act.postcondition(_workbench_image(), {}) is True


# ---------------------------------------------------------------------------
# WaitForBoard
# ---------------------------------------------------------------------------

class TestWaitForBoard:
    def test_postcondition_true_on_bright_image(self):
        """Board visible when mean brightness > 10."""
        from Code.Amiga.Activities import WaitForBoard
        act = WaitForBoard()
        assert act.postcondition(_bright_image(), {}) is True

    def test_postcondition_false_on_black_image(self):
        """Board not visible on all-black screen."""
        from Code.Amiga.Activities import WaitForBoard
        act = WaitForBoard()
        assert act.postcondition(_black_image(), {}) is False


# ---------------------------------------------------------------------------
# AdvancePastTitle
# ---------------------------------------------------------------------------

class TestAdvancePastTitle:
    def test_precondition_true_on_bright_image(self):
        """precondition True when title is visible (bright image)."""
        from Code.Amiga.Activities import AdvancePastTitle
        act = AdvancePastTitle()
        assert act.precondition(_bright_image(), {}) is True

    def test_precondition_false_on_black_image(self):
        """precondition False when screen is blank."""
        from Code.Amiga.Activities import AdvancePastTitle
        act = AdvancePastTitle()
        assert act.precondition(_black_image(), {}) is False

    def test_execute_sends_two_enter_keypresses(self):
        """execute() sends two Enter (keycode 36) keypresses."""
        from Code.Amiga.Activities import AdvancePastTitle
        driver = FakeDriver([_bright_image()])
        act = AdvancePastTitle()
        # Patch time.sleep so the test does not actually sleep 0.5 s
        import unittest.mock as mock
        with mock.patch("Code.Amiga.Activities.time.sleep"):
            act.execute(driver, {})
        assert driver.keys.count(36) == 2

    def test_postcondition_true_on_bright_image(self):
        """postcondition True once board/menu content is visible."""
        from Code.Amiga.Activities import AdvancePastTitle
        act = AdvancePastTitle()
        assert act.postcondition(_bright_image(), {}) is True


# ---------------------------------------------------------------------------
# AdvancePastCopyrightScreen
# ---------------------------------------------------------------------------

def _workbench_image() -> Any:
    """Image with mean brightness ~8 — simulates the Workbench dark desktop.

    Real Workbench screenshot has mean ~7.5.  Above 4.0 (WaitForTitle threshold)
    but below 10.0 (LaunchBattleChessFromWorkbench postcondition threshold).
    """
    return _solid_rgb_image(8, 8, 8)


def _yellow_dialog_image() -> Any:
    """Image with a yellow rectangle in the dialog region — dialog visible."""
    from PIL import Image
    import numpy as np
    # Start with a bright grey (represents 3D board content)
    img = Image.new("RGB", (640, 400), (100, 100, 100))
    # Paint yellow in the dialog region: x=150..410, y=215..280
    # Yellow = (R>150, G>120, B<100)
    arr = np.array(img)
    arr[215:280, 150:410] = [200, 180, 50]  # yellow-ish
    return Image.fromarray(arr.astype("uint8"))


class TestAdvancePastCopyrightScreen:
    def test_dialog_visible_on_yellow_region(self):
        """_dialog_visible returns True when yellow region is in dialog area."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        assert AdvancePastCopyrightScreen._dialog_visible(_yellow_dialog_image()) is True

    def test_dialog_not_visible_on_grey_image(self):
        """_dialog_visible returns False when no yellow region present."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        assert AdvancePastCopyrightScreen._dialog_visible(_bright_image()) is False

    def test_dialog_not_visible_on_none(self):
        """_dialog_visible returns False on None."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        assert AdvancePastCopyrightScreen._dialog_visible(None) is False

    def test_precondition_true_when_board_and_dialog_visible(self):
        """precondition True when board visible AND yellow dialog present."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        act = AdvancePastCopyrightScreen()
        assert act.precondition(_yellow_dialog_image(), {}) is True

    def test_precondition_false_when_no_dialog(self):
        """precondition False when board visible but no dialog."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        act = AdvancePastCopyrightScreen()
        assert act.precondition(_bright_image(), {}) is False

    def test_precondition_false_on_black_image(self):
        """precondition False when board not visible."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        act = AdvancePastCopyrightScreen()
        assert act.precondition(_black_image(), {}) is False

    def test_execute_sends_enter_until_dialog_gone(self):
        """execute() sends Enter repeatedly; stops early when dialog disappears."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        import unittest.mock as mock
        act = AdvancePastCopyrightScreen()
        # Driver returns: dialog image 3 times, then non-dialog (bright grey)
        driver = FakeDriver(
            [_yellow_dialog_image()] * 3 + [_bright_image()] * 10
        )
        with mock.patch("Code.Amiga.Activities.time.sleep"):
            act.execute(driver, {})
        # At minimum 4 Enter keypresses (3 dialog + 1 after it clears)
        assert driver.keys.count(36) >= 1

    def test_postcondition_true_when_dialog_gone(self):
        """postcondition True when screenshot shows no dialog."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        act = AdvancePastCopyrightScreen()
        assert act.postcondition(_bright_image(), {}) is True

    def test_postcondition_false_when_dialog_still_visible(self):
        """postcondition False when dialog still present."""
        from Code.Amiga.Activities import AdvancePastCopyrightScreen
        act = AdvancePastCopyrightScreen()
        assert act.postcondition(_yellow_dialog_image(), {}) is False


# ---------------------------------------------------------------------------
# StartNewGame
# ---------------------------------------------------------------------------

class TestStartNewGame:
    def test_precondition_true_when_board_visible_no_dialog(self):
        """precondition True when board visible and no copyright dialog."""
        from Code.Amiga.Activities import StartNewGame
        act = StartNewGame()
        # bright grey = board visible, no yellow dialog
        assert act.precondition(_bright_image(), {}) is True

    def test_precondition_false_when_dialog_visible(self):
        """precondition False when copyright dialog is still showing."""
        from Code.Amiga.Activities import StartNewGame
        act = StartNewGame()
        assert act.precondition(_yellow_dialog_image(), {}) is False

    def test_precondition_false_on_black_image(self):
        """precondition False when board is not visible."""
        from Code.Amiga.Activities import StartNewGame
        act = StartNewGame()
        assert act.precondition(_black_image(), {}) is False

    def test_execute_clicks_board_center(self):
        """execute() sends a click at board centre coordinates."""
        from Code.Amiga.Activities import StartNewGame
        import unittest.mock as mock
        act = StartNewGame()
        driver = FakeDriver([_bright_image()])
        with mock.patch("Code.Amiga.Activities.time.sleep"):
            act.execute(driver, {})
        assert len(driver.clicks) == 1
        x, y = driver.clicks[0]
        assert x == StartNewGame._BOARD_CENTER_X
        assert y == StartNewGame._BOARD_CENTER_Y

    def test_postcondition_true_when_board_visible(self):
        """postcondition True when board is still showing after click."""
        from Code.Amiga.Activities import StartNewGame
        act = StartNewGame()
        assert act.postcondition(_bright_image(), {}) is True

    def test_postcondition_false_on_black_screen(self):
        """postcondition False when screen goes blank (unexpected crash/reset)."""
        from Code.Amiga.Activities import StartNewGame
        act = StartNewGame()
        assert act.postcondition(_black_image(), {}) is False


# ---------------------------------------------------------------------------
# PlayMove — geometry not calibrated path
# ---------------------------------------------------------------------------

class TestPlayMoveUncalibrated:
    def test_precondition_requires_board_visible(self):
        """precondition False on blank screen."""
        from Code.Amiga.Activities import PlayMove
        act = PlayMove("e2", "e4")
        assert act.precondition(_black_image(), {}) is False

    def test_precondition_true_on_bright_image(self):
        """precondition True when board is visible; also sets pre_move_img."""
        from Code.Amiga.Activities import PlayMove
        act = PlayMove("e2", "e4")
        ctx: dict = {}
        img = _bright_image()
        result = act.precondition(img, ctx)
        assert result is True
        assert ctx.get("pre_move_img") is img

    def test_postcondition_true_when_uncalibrated(self):
        """postcondition falls back to True when geometry is not calibrated."""
        from Code.Amiga.Activities import PlayMove
        import Code.Amiga.BattleChess as bc
        # Ensure geometry is NOT calibrated
        bc._SQ_HALF_W = None
        bc._SQ_HALF_H = None
        act = PlayMove("e2", "e4")
        ctx = {"pre_move_img": _bright_image()}
        assert act.postcondition(_bright_image(), ctx) is True


# ---------------------------------------------------------------------------
# WaitForComputerReply
# ---------------------------------------------------------------------------

class TestWaitForComputerReply:
    def test_precondition_sets_baseline_when_missing(self):
        """precondition captures after_our_move baseline on first call."""
        from Code.Amiga.Activities import WaitForComputerReply
        act = WaitForComputerReply()
        ctx: dict = {}
        img = _bright_image()
        result = act.precondition(img, ctx)
        assert result is True
        assert "after_our_move" in ctx

    def test_precondition_false_on_black_image(self):
        """precondition False when board is not visible."""
        from Code.Amiga.Activities import WaitForComputerReply
        act = WaitForComputerReply()
        assert act.precondition(_black_image(), {}) is False

    def test_postcondition_false_when_no_change(self):
        """postcondition False when before and after images are identical."""
        from Code.Amiga.Activities import WaitForComputerReply
        import Code.Amiga.BattleChess as bc
        bc._BOARD_REGION = None
        act = WaitForComputerReply()
        img = _bright_image()
        ctx = {"after_our_move": img}
        # Same image repeated — no change
        assert act.postcondition(img, ctx) is False

    def test_postcondition_true_when_board_changes(self):
        """postcondition True when the image differs from baseline."""
        from Code.Amiga.Activities import WaitForComputerReply
        import Code.Amiga.BattleChess as bc
        bc._BOARD_REGION = None
        act = WaitForComputerReply()
        before = _solid_rgb_image(80, 80, 80)
        after  = _solid_rgb_image(120, 100, 90)  # significantly brighter
        ctx = {"after_our_move": before}
        assert act.postcondition(after, ctx) is True

    def test_postcondition_false_when_no_baseline(self):
        """postcondition False when ctx lacks after_our_move."""
        from Code.Amiga.Activities import WaitForComputerReply
        act = WaitForComputerReply()
        assert act.postcondition(_bright_image(), {}) is False


# ---------------------------------------------------------------------------
# ExtractComputerMove
# ---------------------------------------------------------------------------

class TestExtractComputerMove:
    def test_precondition_requires_baseline_and_board(self):
        """precondition False when after_our_move is missing from ctx."""
        from Code.Amiga.Activities import ExtractComputerMove
        act = ExtractComputerMove()
        ctx: dict = {}
        assert act.precondition(_bright_image(), ctx) is False

    def test_precondition_true_with_baseline_and_bright_image(self):
        """precondition True when baseline exists and board visible."""
        from Code.Amiga.Activities import ExtractComputerMove
        act = ExtractComputerMove()
        ctx = {"after_our_move": _bright_image()}
        assert act.precondition(_bright_image(), ctx) is True

    def test_execute_captures_screenshot_into_ctx(self):
        """execute() stores after_cpu_move in ctx via driver.screenshot()."""
        from Code.Amiga.Activities import ExtractComputerMove
        img = _bright_image()
        driver = FakeDriver([img])
        act = ExtractComputerMove()
        ctx: dict = {}
        act.execute(driver, ctx)
        assert "after_cpu_move" in ctx

    def test_postcondition_none_when_uncalibrated(self):
        """postcondition True (stub pass) and sets computer_move=None when geometry unset."""
        from Code.Amiga.Activities import ExtractComputerMove
        import Code.Amiga.BattleChess as bc
        bc._SQ_HALF_W = None
        bc._SQ_HALF_H = None
        act = ExtractComputerMove()
        ctx = {"after_our_move": _bright_image(), "after_cpu_move": _bright_image()}
        result = act.postcondition(None, ctx)
        assert result is True
        assert ctx.get("computer_move") is None

    def test_postcondition_false_when_ctx_missing_cpu_move(self):
        """postcondition False when after_cpu_move not in ctx."""
        from Code.Amiga.Activities import ExtractComputerMove
        act = ExtractComputerMove()
        ctx = {"after_our_move": _bright_image()}
        assert act.postcondition(None, ctx) is False


# ---------------------------------------------------------------------------
# AmigaRunner — integration over fake activities
# ---------------------------------------------------------------------------

class _AlwaysPassActivity(AmigaActivity if False else object):
    """Fake activity where everything succeeds immediately."""

    name = "AlwaysPass"
    settle_ms = 0
    verify_ms = 500
    check_pre_screenshot = False
    verify_screenshot = False

    def precondition(self, img, ctx):
        return True

    def execute(self, driver, ctx):
        ctx["executed"] = ctx.get("executed", 0) + 1

    def postcondition(self, img, ctx):
        return True


class _AlwaysFailPreActivity(_AlwaysPassActivity):
    """Fake activity whose precondition always fails."""

    name = "AlwaysFailPre"

    def precondition(self, img, ctx):
        return False


class _AlwaysFailPostActivity(_AlwaysPassActivity):
    """Fake activity whose postcondition always fails."""

    name = "AlwaysFailPost"
    verify_screenshot = True

    def postcondition(self, img, ctx):
        return False


class TestAmigaRunner:
    def test_run_executes_all_activities(self):
        """Runner calls execute() on each activity in sequence."""
        from Code.Amiga.Activities import AmigaRunner
        # Re-import AmigaActivity base so the fake subclasses work correctly
        from Code.Amiga.Activities import AmigaActivity

        class _Pass(AmigaActivity):
            name = "Pass"
            settle_ms = 0
            verify_ms = 100
            check_pre_screenshot = False
            verify_screenshot = False

            def precondition(self, img, ctx): return True
            def execute(self, driver, ctx): ctx["n"] = ctx.get("n", 0) + 1
            def postcondition(self, img, ctx): return True

        driver = FakeDriver([_bright_image()] * 10)
        ctx = AmigaRunner().run(driver, [_Pass(), _Pass(), _Pass()])
        assert ctx["n"] == 3

    def test_run_raises_on_precondition_fail(self):
        """Runner raises RuntimeError when precondition returns False."""
        from Code.Amiga.Activities import AmigaRunner, AmigaActivity

        class _FailPre(AmigaActivity):
            name = "FailPre"
            settle_ms = 0
            verify_ms = 100
            check_pre_screenshot = False
            verify_screenshot = False

            def precondition(self, img, ctx): return False
            def execute(self, driver, ctx): pass
            def postcondition(self, img, ctx): return True

        driver = FakeDriver([_bright_image()] * 5)
        with pytest.raises(RuntimeError, match="precondition failed"):
            AmigaRunner().run(driver, [_FailPre()])

    def test_run_raises_on_postcondition_timeout(self):
        """Runner raises RuntimeError when postcondition never becomes True."""
        from Code.Amiga.Activities import AmigaRunner, AmigaActivity

        class _FailPost(AmigaActivity):
            name = "FailPost"
            settle_ms = 0
            verify_ms = 100   # short timeout so test is fast
            check_pre_screenshot = False
            verify_screenshot = True

            def precondition(self, img, ctx): return True
            def execute(self, driver, ctx): pass
            def postcondition(self, img, ctx): return False

        driver = FakeDriver([_bright_image()] * 50)
        with pytest.raises(RuntimeError, match="postcondition timed out"):
            AmigaRunner().run(driver, [_FailPost()])


# ---------------------------------------------------------------------------
# FsUaeDriver._cursor_pos — cursor detection unit tests
# ---------------------------------------------------------------------------

def _image_with_red_pixel(x: int, y: int, w: int = 640, h: int = 432):
    """Return a grey image with a single bright-red pixel at (x, y)."""
    from PIL import Image
    img = Image.new("RGB", (w, h), (80, 80, 80))
    img.putpixel((x, y), (200, 50, 40))
    return img


def _image_with_red_cluster(cx: int, cy: int, size: int = 5, w: int = 640, h: int = 432):
    """Return a grey image with a small red cluster (cursor arrow tip simulation)."""
    from PIL import Image
    img = Image.new("RGB", (w, h), (80, 80, 80))
    for dy in range(size):
        for dx in range(size - dy):
            img.putpixel((cx + dx, cy + dy), (200, 50, 40))
    return img


class TestFsUaeDriverCursorPos:
    """Unit tests for FsUaeDriver._cursor_pos (cursor tip detection)."""

    def _make_driver(self):
        """Return a FsUaeDriver instance without a real process."""
        from Code.Amiga.Driver import FsUaeDriver
        drv = object.__new__(FsUaeDriver)
        return drv

    def test_returns_none_on_solid_grey_image(self):
        """No red pixels → None."""
        drv = self._make_driver()
        img = _solid_rgb_image(80, 80, 80)
        assert drv._cursor_pos(img) is None

    def test_returns_none_when_too_few_red_pixels(self):
        """Fewer than 3 red pixels → None (avoids noise false positives)."""
        drv = self._make_driver()
        from PIL import Image
        img = Image.new("RGB", (640, 432), (80, 80, 80))
        img.putpixel((100, 100), (200, 50, 40))
        img.putpixel((200, 200), (200, 50, 40))
        assert drv._cursor_pos(img) is None

    def test_detects_topmost_red_pixel_as_tip(self):
        """Cursor tip is the topmost (smallest y) red pixel."""
        drv = self._make_driver()
        img = _image_with_red_cluster(cx=150, cy=80)
        pos = drv._cursor_pos(img)
        assert pos is not None
        x, y = pos
        assert y == 80
        assert x == 150

    def test_detects_tip_with_red_cluster(self):
        """Cursor arrow cluster: topmost-leftmost pixel is tip."""
        drv = self._make_driver()
        img = _image_with_red_cluster(cx=200, cy=60, size=8)
        pos = drv._cursor_pos(img)
        assert pos is not None
        _, y = pos
        assert y == 60

    def test_not_confused_by_non_red_pixels(self):
        """Green pixels are ignored; only R>150, G<100, B<100 qualifies."""
        drv = self._make_driver()
        from PIL import Image
        img = Image.new("RGB", (640, 432), (80, 80, 80))
        for i in range(20):
            img.putpixel((i, 50), (50, 200, 50))  # green — not red
        for i in range(5):
            img.putpixel((300, 200 + i), (200, 50, 40))  # actual red cluster
        pos = drv._cursor_pos(img)
        assert pos is not None
        _, y = pos
        assert y == 200
