"""
pytest fixtures for Caissa UI integration tests.

The session-scoped ``client`` fixture launches the app once, waits for it to be
ready, and tears it down after all UI tests complete.  The ``config_theme`` fixture
changes ``x_style_mode`` before a test and restores it afterwards.

Environment:
    CAISSA_REPO   Path to the repository root (defaults to the parent of this file's
                  grandparent directory, i.e. the repo root when tests run from there).
    CAISSA_TIMEOUT  Seconds to wait for the app to become ready (default 30).
"""

import os
import signal
import subprocess
import time

import pytest

from tests.ui.client import CaissaClient

_REPO = os.environ.get(
    "CAISSA_REPO",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)
_LAUNCH_SCRIPT = os.path.join(_REPO, "tools", "caissa")
_READY_TIMEOUT = float(os.environ.get("CAISSA_TIMEOUT", "30"))


def _kill_existing():
    """Kill any running Caissa process so we start clean."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "LucasR.py"],
            capture_output=True, text=True
        )
        for pid in result.stdout.strip().split():
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ProcessLookupError, ValueError):
                pass
        # Give them time to exit
        time.sleep(1.5)
    except Exception:
        pass


def _disable_startup_dialogs():
    """
    Patch the config pickle to suppress startup dialogs before launch.

    Sets x_check_for_update and x_show_puzzles_on_startup to False so the app
    starts directly at the home screen without any dialogs that would block tests.
    Returns a restore dict so the original values can be written back after tests.
    """
    import pickle
    pk_path = os.path.join(_REPO, "UserData", "__Config__", "lk.pk2")
    if not os.path.exists(pk_path):
        return {}
    with open(pk_path, "rb") as f:
        cfg = pickle.load(f)
    original = {
        "x_check_for_update": cfg.get("x_check_for_update"),
        "x_show_puzzles_on_startup": cfg.get("x_show_puzzles_on_startup"),
    }
    cfg["x_check_for_update"] = False
    cfg["x_show_puzzles_on_startup"] = False
    with open(pk_path, "wb") as f:
        pickle.dump(cfg, f)
    return original


def _restore_startup_config(original: dict):
    """Restore config values changed by _disable_startup_dialogs."""
    if not original:
        return
    import pickle
    pk_path = os.path.join(_REPO, "UserData", "__Config__", "lk.pk2")
    if not os.path.exists(pk_path):
        return
    with open(pk_path, "rb") as f:
        cfg = pickle.load(f)
    for k, v in original.items():
        if v is not None:
            cfg[k] = v
    with open(pk_path, "wb") as f:
        pickle.dump(cfg, f)


@pytest.fixture(scope="session")
def caissa_proc():
    """
    Session-scoped fixture: launch Caissa once, yield its Popen handle, then stop it.

    Kills any existing Caissa process before launch so we always start from a known
    state.  Disables startup dialogs via pickle manipulation so the app starts at the
    home screen without any blocking dialogs.
    """
    _kill_existing()
    original_config = _disable_startup_dialogs()

    env = {**os.environ, "CAISSA_TEST": "1"}
    proc = subprocess.Popen(
        [_LAUNCH_SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=_REPO,
    )

    yield proc

    # Teardown: stop the app
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    _restore_startup_config(original_config)


@pytest.fixture(scope="session")
def client(caissa_proc):
    """
    Session-scoped fixture: return a connected CaissaClient.

    Waits up to CAISSA_TIMEOUT seconds for the app to respond to ping.
    """
    c = CaissaClient()
    c.wait_ready(timeout=_READY_TIMEOUT)
    return c


@pytest.fixture
def config_theme(client):
    """
    Function-scoped fixture factory.

    Usage in test::

        def test_something(client, config_theme):
            config_theme("Caissa")
            ...

    Sets x_style_mode to the requested theme before the test and restores the
    original value after.  Also closes any open dialog before and after to ensure
    a clean state.
    """
    original_theme = None

    def _set_theme(theme_name: str):
        nonlocal original_theme
        info = client.info()
        original_theme = info.get("style_mode")
        if original_theme != theme_name:
            client.send(f"set_config x_style_mode {theme_name}")
        # Dismiss any open dialog so tests start from the home screen
        try:
            client.dialog_cancel()
        except Exception:
            pass

    yield _set_theme

    # Restore
    if original_theme is not None:
        try:
            client.dialog_cancel()
        except Exception:
            pass
        try:
            client.send(f"set_config x_style_mode {original_theme}")
        except Exception:
            pass
