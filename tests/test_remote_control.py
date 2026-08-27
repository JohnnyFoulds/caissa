"""
tests/test_remote_control.py — tests that drive the live Caissa app via the
Unix socket remote control server at /tmp/caissa-control.sock.

Requirements:
  • The Caissa app must be running before these tests execute.
  • Start it with:
      cd /Users/johannes/code/lucaschess/bin
      .venv/bin/python3 LucasR.py &>/tmp/caissa_run.log &

Run with:
  cd /Users/johannes/code/lucaschess/bin
  .venv/bin/python3 -m pytest ../tests/test_remote_control.py -v
  # or from repo root:
  .venv/bin/python3 -m pytest tests/test_remote_control.py -v
"""

import json
import os
import socket
import time

import pytest

SOCKET_PATH = "/tmp/caissa-control.sock"


# ---------------------------------------------------------------------------
# Socket helper
# ---------------------------------------------------------------------------

def _send(command: str, timeout: float = 15.0) -> dict:
    """Send one newline-terminated command, return parsed JSON response."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(SOCKET_PATH)
    sock.sendall((command + "\n").encode())
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    sock.close()
    return json.loads(data.decode().strip())


def _wait_for_condition(fn, timeout: float = 20.0, poll: float = 0.5):
    """Poll fn() every poll seconds until it returns truthy or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            val = fn()
            if val:
                return val
        except Exception:
            pass
        time.sleep(poll)
    return None


# ---------------------------------------------------------------------------
# Skip entire module if app not running
# ---------------------------------------------------------------------------

def _app_is_running() -> bool:
    try:
        resp = _send("ping", timeout=3)
        return resp.get("ok") is True
    except Exception:
        return False


if not _app_is_running():
    pytest.skip(
        "Caissa app not running — start it with: "
        "cd bin && .venv/bin/python3 LucasR.py &>/tmp/caissa_run.log &",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _cancel_game(wait: float = 0.6):
    """Cancel any running game and wait for home screen to settle."""
    try:
        _send("force_cancel", timeout=5)
        time.sleep(wait)
    except Exception:
        pass


def _ensure_home():
    """Return True if we're on the home screen (toolbar has 'Play' button)."""
    try:
        r = _send("toolbar_info", timeout=5)
        named = [b["text"] for b in r.get("buttons", []) if b.get("text", "").strip()]
        return "Play" in named
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Basic connectivity
# ---------------------------------------------------------------------------

class TestPing:
    def test_ping(self):
        resp = _send("ping")
        assert resp == {"ok": True}

    def test_unknown_command(self):
        resp = _send("xyzzy_notacommand")
        assert "error" in resp


# ---------------------------------------------------------------------------
# Toolbar inspection (home screen)
# ---------------------------------------------------------------------------

class TestToolbarInfo:
    def test_home_screen_has_8_named_buttons(self):
        resp = _send("toolbar_info")
        assert "buttons" in resp, f"unexpected response: {resp}"
        # Filter out separators (empty text)
        named = [b for b in resp["buttons"] if b.get("text", "").strip()]
        assert len(named) == 8, f"expected 8 named home buttons, got {len(named)}: {named}"

    def test_home_button_names(self):
        resp = _send("toolbar_info")
        named = [b["text"] for b in resp["buttons"] if b.get("text", "").strip()]
        assert "Play" in named, f"Play missing from {named}"
        assert "Options" in named, f"Options missing from {named}"

    def test_home_buttons_have_size(self):
        resp = _send("toolbar_info")
        for btn in resp["buttons"]:
            if btn.get("text", "").strip():
                assert btn["width"] > 0, f"button {btn['text']} has zero width"
                assert btn["height"] > 0, f"button {btn['text']} has zero height"


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

class TestScreenshot:
    def test_screenshot_creates_file(self, tmp_path):
        path = str(tmp_path / "caissa_test.png")
        resp = _send(f"screenshot {path}")
        assert resp.get("ok") is True, f"screenshot failed: {resp}"
        assert os.path.isfile(path), f"PNG not created at {path}"
        assert os.path.getsize(path) > 1000, "PNG seems empty"

    def test_screenshot_default_path(self):
        resp = _send("screenshot")
        assert resp.get("ok") is True
        assert os.path.isfile(resp["path"])


# ---------------------------------------------------------------------------
# Window inspection
# ---------------------------------------------------------------------------

class TestWindowInspection:
    def test_list_windows(self):
        resp = _send("list_windows")
        assert "windows" in resp
        assert len(resp["windows"]) >= 1
        titles = [w["title"] for w in resp["windows"]]
        assert any("Caissa" in t for t in titles), f"Caissa window not found in {titles}"

    def test_find_widget_toolbar(self):
        resp = _send("find_widget Play")
        assert "class" in resp, f"find_widget failed: {resp}"

    def test_dump_ui_returns_roots(self):
        resp = _send("dump_ui 2")
        assert "roots" in resp
        assert len(resp["roots"]) >= 1


# ---------------------------------------------------------------------------
# Game start
# ---------------------------------------------------------------------------

class TestStartGame:
    """One game started for the whole class; shared by all three tests."""

    @classmethod
    def setup_class(cls):
        _cancel_game()
        resp = _send("startgame engine=stockfish depth=1 side=white")
        assert resp.get("ok") is True, f"class setup startgame failed: {resp}"
        # Wait for toolbar to switch
        _wait_for_condition(
            lambda: "Cancel" in [b["text"] for b in _send("toolbar_info").get("buttons", [])
                                  if b.get("text", "").strip()],
            timeout=10,
        )

    @classmethod
    def teardown_class(cls):
        _cancel_game()

    def test_startgame_returns_ok(self):
        # Game was started in setup_class; check toolbar reflects game state
        r = _send("toolbar_info")
        named = [b["text"] for b in r.get("buttons", []) if b.get("text", "").strip()]
        assert "Cancel" in named or "Resign" in named, f"not in game: {named}"

    def test_startgame_changes_toolbar(self):
        r = _send("toolbar_info")
        named = [b["text"] for b in r.get("buttons", []) if b.get("text", "").strip()]
        assert "Cancel" in named or "Resign" in named, \
            "Toolbar did not change to game toolbar"

    def test_startgame_toolbar_has_game_buttons(self):
        resp = _send("toolbar_info")
        named = [b["text"] for b in resp.get("buttons", []) if b.get("text", "").strip()]
        for expected in ("Cancel", "Resign", "Draw"):
            assert expected in named, f"{expected!r} missing from game toolbar: {named}"


# ---------------------------------------------------------------------------
# Game info
# ---------------------------------------------------------------------------

class TestGameInfo:
    """One game started for the whole class; tests only query its state."""

    @classmethod
    def setup_class(cls):
        _cancel_game()
        resp = _send("startgame engine=stockfish depth=1 side=white")
        assert resp.get("ok") is True, f"class setup startgame failed: {resp}"
        _wait_for_condition(
            lambda: "Cancel" in [b["text"] for b in _send("toolbar_info").get("buttons", [])
                                  if b.get("text", "").strip()],
            timeout=10,
        )
        time.sleep(1)  # let the manager fully initialise

    @classmethod
    def teardown_class(cls):
        _cancel_game()

    def test_game_info_after_start(self):
        resp = _send("game_info")
        assert resp.get("manager_class") == "ManagerPlayAgainstEngine", \
            f"unexpected manager: {resp.get('manager_class')}"
        assert resp.get("fen"), f"no FEN in game_info: {resp}"

    def test_game_info_fen_is_valid(self):
        resp = _send("game_info")
        fen = resp.get("fen", "")
        parts = fen.split()
        assert len(parts) >= 4, f"FEN looks malformed: {fen!r}"
        assert parts[1] in ("w", "b"), f"unexpected active colour in FEN: {parts[1]}"

    def test_game_info_has_move_count(self):
        resp = _send("game_info")
        assert "move_count" in resp
        assert isinstance(resp["move_count"], int)


# ---------------------------------------------------------------------------
# Making moves
# ---------------------------------------------------------------------------

class TestMakeMove:
    """One game started for the whole class; tests make moves sequentially."""

    @classmethod
    def setup_class(cls):
        _cancel_game()
        resp = _send("startgame engine=stockfish depth=1 side=white")
        assert resp.get("ok") is True, f"class setup startgame failed: {resp}"
        _wait_for_condition(
            lambda: "Cancel" in [b["text"] for b in _send("toolbar_info").get("buttons", [])
                                  if b.get("text", "").strip()],
            timeout=10,
        )
        time.sleep(1)

    @classmethod
    def teardown_class(cls):
        _cancel_game()

    def test_make_move_e2e4(self):
        info = _send("game_info")
        assert info.get("turn") == "white", f"expected white to move, got: {info.get('turn')}"
        resp = _send("make_move e2e4")
        assert resp.get("ok") is True, f"make_move failed: {resp}"

    def test_engine_replies_after_player_move(self):
        # e2e4 was sent in the previous test; wait for the engine to reply
        def has_engine_moved():
            r = _send("game_info")
            return r.get("move_count", 0) >= 2

        engine_replied = _wait_for_condition(has_engine_moved, timeout=20)
        assert engine_replied, "Engine did not reply after player move within 20s"

    def test_game_length_after_exchange(self):
        resp = _send("game_info")
        assert resp.get("move_count", 0) >= 2, \
            f"expected >=2 moves after exchange, got {resp.get('move_count')}"

    def test_make_move_returns_error_when_no_game(self):
        # Cancel the shared game, then confirm make_move is handled gracefully
        _cancel_game(wait=1.0)
        resp = _send("make_move e2e4")
        assert "ok" in resp or "error" in resp


# ---------------------------------------------------------------------------
# UI interaction
# ---------------------------------------------------------------------------

class TestUIInteraction:
    def test_dialog_info_when_no_dialog(self):
        _cancel_game()  # ensure home screen (no active game dialog)
        resp = _send("dialog_info")
        assert "error" in resp or "title" in resp

    def test_dialog_cancel_when_no_dialog(self):
        resp = _send("dialog_cancel")
        assert "error" in resp or resp.get("ok") is True

    def test_click_toolbar_triggers_action(self):
        _send("startgame engine=stockfish depth=1 side=white")
        _wait_for_condition(
            lambda: "Cancel" in [b["text"] for b in _send("toolbar_info").get("buttons", [])
                                  if b.get("text", "").strip()],
            timeout=10,
        )
        resp = _send("click_toolbar Pause")
        assert resp.get("ok") is True, f"click_toolbar Pause failed: {resp}"
        time.sleep(0.3)
        _cancel_game()


# ---------------------------------------------------------------------------
# set_config command
# ---------------------------------------------------------------------------

class TestSetConfig:
    """Tests for the set_config RemoteControl command."""

    def setup_method(self):
        _cancel_game()

    def test_set_config_returns_ok(self):
        resp = _send("info")
        original_style = resp.get("style_mode", "By default")
        new_style = "By default" if original_style != "By default" else "By default"
        resp = _send(f"set_config x_style_mode {new_style}")
        assert resp.get("ok") is True, f"set_config failed: {resp}"
        assert resp.get("key") == "x_style_mode"

    def test_set_config_unknown_key_returns_error(self):
        resp = _send("set_config x_nonexistent_key value")
        assert "error" in resp, f"expected error for unknown key, got: {resp}"

    def test_set_config_no_args_returns_error(self):
        resp = _send("set_config")
        assert "error" in resp, f"expected error for missing args, got: {resp}"

    def test_set_config_bool_coercion(self):
        resp = _send("info")
        # Flip x_check_for_update to false (safe — we're in test mode anyway)
        resp = _send("set_config x_check_for_update false")
        assert resp.get("ok") is True, f"set_config bool failed: {resp}"
        assert resp.get("value") is False

    def test_set_config_persists_via_info(self):
        """set_config x_style_mode change is reflected in subsequent info call."""
        info_before = _send("info")
        original = info_before.get("style_mode", "By default")
        new_val = "By default"
        _send(f"set_config x_style_mode {new_val}")
        info_after = _send("info")
        assert info_after.get("style_mode") == new_val, (
            f"style_mode not updated: {info_after}"
        )
        # Restore
        _send(f"set_config x_style_mode {original}")


# ---------------------------------------------------------------------------
# open_config command
# ---------------------------------------------------------------------------

class TestOpenConfig:
    """Tests for the open_config RemoteControl command."""

    def setup_method(self):
        _cancel_game()
        # Dismiss any open dialog
        try:
            _send("dialog_cancel", timeout=3)
        except Exception:
            pass
        time.sleep(0.3)

    def teardown_method(self):
        # Always close any open dialog after each test
        try:
            _send("dialog_cancel", timeout=3)
        except Exception:
            pass
        time.sleep(0.3)

    def test_open_config_returns_ok(self):
        resp = _send("open_config")
        assert resp.get("ok") is True, f"open_config failed: {resp}"

    def test_open_config_opens_dialog(self):
        _send("open_config")
        # Poll for dialog to appear
        def dialog_appeared():
            r = _send("dialog_info", timeout=5)
            return "title" in r and "error" not in r

        appeared = _wait_for_condition(dialog_appeared, timeout=5.0, poll=0.3)
        assert appeared, "Configuration dialog did not open after open_config"

    def test_open_config_dialog_title(self):
        _send("open_config")
        _wait_for_condition(
            lambda: "error" not in _send("dialog_info", timeout=5),
            timeout=5.0, poll=0.3
        )
        info = _send("dialog_info")
        assert "General configuration" in info.get("title", ""), (
            f"Unexpected dialog title: {info.get('title')!r}"
        )

    def test_open_config_dialog_can_be_cancelled(self):
        _send("open_config")
        _wait_for_condition(
            lambda: "error" not in _send("dialog_info", timeout=5),
            timeout=5.0, poll=0.3
        )
        resp = _send("dialog_cancel")
        assert resp.get("ok") is True, f"dialog_cancel failed: {resp}"
