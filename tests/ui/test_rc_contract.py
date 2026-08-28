"""
Phase 2-A — RemoteControl wire-contract regression gate.

Records the response key structure for all 25 dispatch-table verbs against the
pre-Phase-2 binary and asserts that the key sets are preserved after the Phase-2
refactor (extraction of QtDriver helpers).

All 25 dispatch verbs are covered:
  ping / info / themes / theme / screenshot / menu / action / toolbar_info /
  list_windows / dump_ui / find_widget / click_widget / click_toolbar /
  click_tab / set_field / combo_select / dialog_info / dialog_accept /
  dialog_cancel / set_config / open_config / force_cancel /
  startgame / make_move / game_info

Tests use a raw socket helper (not CaissaClient.send) so error-path responses
--- where the expected response IS ``{"error": "..."}`` --- are returned as dicts
rather than raising CaissaClientError.

These tests require a running Caissa process at /tmp/caissa-control.sock and are
skipped automatically when no live app is present.  They do NOT use the
caissa_proc fixture (which launches a new process); they connect to whatever
app is already running.  This is intentional: Phase 2-A must record the
pre-refactor binary, and the conftest fixture cannot launch the binary from the
worktree because the worktree has LFS stubs.
"""

import json
import socket
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

SOCKET_PATH = "/tmp/caissa-control.sock"

_CONTRACT_FILE = Path(__file__).parent / "rc_contract.json"
with _CONTRACT_FILE.open() as _f:
    _CONTRACT = json.load(_f)

_ALL_PROBES = {p["id"]: p for p in _CONTRACT["probes"]}
_STATELESS = [p for p in _CONTRACT["probes"] if not p["requires_game"]]


# ---------------------------------------------------------------------------
# Raw transport — does NOT raise on error-keyed responses
# ---------------------------------------------------------------------------

def _raw_call(cmd: str, timeout: float = 10.0) -> dict:
    """Send ``cmd`` to the live socket and return the parsed JSON dict."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(SOCKET_PATH)
    try:
        s.sendall((cmd + "\n").encode())
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
    finally:
        s.close()
    return json.loads(data.strip())


def _reset_to_home():
    """Ensure the app is at the home screen with no active game."""
    _raw_call("force_cancel")
    time.sleep(0.5)  # force_cancel defers proc.start() by 300ms


@pytest.fixture(scope="module", autouse=True)
def require_live_app():
    """Skip the entire module if no live Caissa app is reachable."""
    try:
        resp = _raw_call("ping", timeout=3.0)
        assert resp == {"ok": True}
    except Exception as exc:
        pytest.skip(f"No live Caissa app at {SOCKET_PATH}: {exc}")


# ---------------------------------------------------------------------------
# Stateless probes — 22 verbs that require no game setup
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "probe",
    _STATELESS,
    ids=[p["id"] for p in _STATELESS],
)
def test_verb_response_keys_match_golden(probe):
    """
    Response key set must match the golden fixture for each stateless verb.

    :param probe: Probe entry from rc_contract.json.
    """
    resp = _raw_call(probe["cmd"])
    assert set(resp.keys()) == set(probe["keys"]), (
        f"Probe {probe['id']!r}: expected keys {sorted(probe['keys'])} "
        f"but got {sorted(resp.keys())}  (full response: {resp})"
    )


# ---------------------------------------------------------------------------
# Game-state probes — 3 verbs that require an active game
# ---------------------------------------------------------------------------

def test_game_verb_response_keys():
    """
    Response key sets for startgame / make_move / game_info must match golden.

    Runs verbs in the correct sequence:
      1. force_cancel → clean home state
      2. startgame (probe)
      3. make_move e2e4 (probe)
      4. game_info (probe)
      5. force_cancel → restore home state
    """
    _reset_to_home()

    # --- startgame ---
    probe = _ALL_PROBES["startgame"]
    resp = _raw_call(probe["cmd"])
    assert set(resp.keys()) == set(probe["keys"]), (
        f"startgame: expected keys {sorted(probe['keys'])} "
        f"but got {sorted(resp.keys())}  (full: {resp})"
    )
    time.sleep(0.3)

    # --- make_move ---
    probe = _ALL_PROBES["make_move"]
    resp = _raw_call(probe["cmd"])
    assert set(resp.keys()) == set(probe["keys"]), (
        f"make_move: expected keys {sorted(probe['keys'])} "
        f"but got {sorted(resp.keys())}  (full: {resp})"
    )

    # --- game_info ---
    probe = _ALL_PROBES["game_info"]
    resp = _raw_call(probe["cmd"])
    assert set(resp.keys()) == set(probe["keys"]), (
        f"game_info: expected keys {sorted(probe['keys'])} "
        f"but got {sorted(resp.keys())}  (full: {resp})"
    )

    # Restore home screen
    _reset_to_home()
