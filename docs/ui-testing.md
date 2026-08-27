# UI Testing Framework — Software Design Document

**Status:** Specified — implementation in `tests/ui/`  
**Branch:** `feat/ui-testing-framework`

---

## 1. Problem statement

Visual UI features — label renames, hidden fields, tab renames from the overlay system;
Coach landing screen cards; mode switching — cannot be verified by unit tests alone.  
The unit test suite runs without a display and without Qt, so it can only test logic that
operates on data structures. The *rendered result* is invisible to it.

Ad-hoc approaches (AppleScript, raw AppKit coordinate-clicking) are fragile, require
special permissions, and cannot be tested or reproduced deterministically. A proper
integration test framework is needed that:

1. Launches the real app process
2. Controls and inspects it through a stable, documented channel
3. Asserts on widget state, not pixel colours
4. Runs in a single `pytest` invocation without manual setup

---

## 2. Existing infrastructure

`bin/Code/Debug/RemoteControl.py` already implements a **Unix socket server** embedded in
the Qt process. Commands are newline-terminated JSON-over-socket; responses are JSON.
`tools/caissa-ctl` is the CLI client. This is the right channel — it is platform-
independent, doesn't require screen-recording permissions, and is already battle-tested.

Available commands relevant to UI testing:

| Command | Use |
|---|---|
| `ping` | confirm app is ready |
| `info` | current theme / style / icons |
| `screenshot <path>` | save window PNG |
| `click_toolbar <text>` | trigger a toolbar button by action text |
| `dialog_info` | list all widgets in the topmost modal dialog |
| `dialog_accept` | click OK in topmost modal dialog |
| `dialog_cancel` | click Cancel in topmost modal dialog |
| `click_tab <text>` | switch to a tab in the topmost QTabWidget |
| `combo_select <query> <value>` | set a QComboBox to a value |
| `find_widget <query>` | assert a widget exists |
| `dump_ui [depth]` | full widget tree snapshot |

---

## 3. Architecture

```
tests/
├─ ui/
│  ├─ conftest.py           # pytest fixtures: launch_app, caissa_client
│  ├─ client.py             # CaissaClient — socket wrapper with retry + assertions
│  ├─ test_overlay.py       # overlay system: label renames, hidden fields, tab renames
│  ├─ test_classical.py     # classical invariant: all original labels present
│  └─ test_config_save.py   # end-to-end: open dialog, change a field, close, verify saved
└─ unit/
   └─ test_form_overlay.py  # already implemented (no-Qt isolation tests)
```

### 3.1 `CaissaClient`

A thin Python class wrapping the Unix socket:

```python
class CaissaClient:
    SOCKET = "/tmp/caissa-control.sock"

    def send(self, cmd: str, timeout: float = 10.0) -> dict
    def wait_ready(self, timeout: float = 30.0) -> None
    def screenshot(self, path: str) -> str
    def dialog_info(self) -> dict
    def dialog_accept(self) -> dict
    def dialog_cancel(self) -> dict
    def click_toolbar(self, text: str) -> dict
    def click_tab(self, text: str) -> dict
    def combo_select(self, query: str, value: str) -> dict
    def find_widget(self, query: str) -> dict
    def assert_widget_exists(self, query: str) -> None
    def assert_widget_absent(self, query: str) -> None
    def assert_dialog_field(self, label: str) -> None
    def assert_dialog_field_absent(self, label: str) -> None
    def assert_tab_exists(self, label: str) -> None
```

All methods that call the socket raise `AssertionError` on error responses so they
integrate naturally with `pytest`.

### 3.2 `conftest.py` — pytest fixtures

```python
@pytest.fixture(scope="session")
def caissa_proc():
    """Launch Caissa; yield; kill on teardown."""

@pytest.fixture(scope="session")
def client(caissa_proc):
    """CaissaClient connected to the session process."""

@pytest.fixture
def config_theme(client, request):
    """Set x_style_mode to the requested theme before the test; restore after."""
```

The `caissa_proc` fixture:
1. Ensures no other Caissa process is running
2. Launches `tools/caissa` with `CAISSA_TEST=1` env var
3. Calls `client.wait_ready()` (polls `ping` until response or timeout)
4. Yields the `subprocess.Popen` handle
5. On teardown: sends `SIGTERM`, waits up to 5 s, then `SIGKILL`

`scope="session"` means the app starts once for the whole test run.

### 3.3 App-side test mode guard

When `CAISSA_TEST=1`, the app:
- Does not show the startup puzzle dialog
- Does not show the first-time config dialog
- Skips the engine check at startup (avoids the 42 s stall)

This is a one-line guard in `LucasChessGui.py`:

```python
if not os.environ.get("CAISSA_TEST"):
    procesador.run_action("new_game_dialog")  # or whatever causes the startup dialogs
```

The exact startup flow to suppress is identified during implementation.

---

## 4. Test specifications

### 4.1 `test_overlay.py` — Caissa theme overlay

All tests in this file use `config_theme("Caissa")` fixture.

**T-OVL-01** — label rename: Mode → Theme

> Given the app is running with the Caissa theme  
> When the Configuration dialog is opened  
> Then a combobox labelled "Theme" is present in the General tab  
> And no combobox labelled "Mode" is present in the General tab

**T-OVL-02** — label rename: UI mode → Mode

> Given the app is running with the Caissa theme  
> When the Configuration dialog is opened  
> Then a combobox labelled "Mode" is present in the General tab

**T-OVL-03** — field hidden: Window style

> Given the app is running with the Caissa theme  
> When the Configuration dialog is opened  
> Then no field labelled "Window style" is present

**T-OVL-04** — field hidden: Menu Play

> Given the app is running with the Caissa theme  
> When the Configuration dialog is opened  
> Then no field labelled "Menu Play" is present

**T-OVL-05** — field hidden: Preventing system crashes when playing

> Given the app is running with the Caissa theme  
> When the Configuration dialog is opened  
> Then no field labelled "Preventing system crashes when playing" is present

**T-OVL-06** — tab rename: Boards 1 → Pieces

> Given the app is running with the Caissa theme  
> When the Configuration dialog is opened  
> Then a tab labelled "Pieces" is present  
> And no tab labelled "Boards 1" is present

**T-OVL-07** — tab rename suite (Boards 2→Board, Appearance 1→Layout, Appearance 2→Colours, Change elos→Rating)

**T-OVL-08** — values survive round-trip

> Given the app is in Caissa theme  
> When the Configuration dialog is opened, the player name is changed, and OK is clicked  
> Then the saved config has the new player name

### 4.2 `test_classical.py` — classical invariant

All tests in this file use `config_theme("By default")` fixture (no overlay).

**T-CLS-01** — all original General tab labels present

> Given the app is running with the "By default" theme  
> When the Configuration dialog is opened  
> Then "Mode", "UI mode", "Window style", "Menu Play", "Preventing system crashes when playing" are all present

**T-CLS-02** — all original tab names present

> "Boards 1", "Boards 2", "Appearance 1", "Appearance 2", "Change elos" all present

---

## 5. Non-functional constraints (N)

- **No special OS permissions required.** The socket does not require Accessibility access.
  Tests fail gracefully (not with a permission error) if the socket is absent.
- **Tests run in < 60 s total** for the full UI suite (excluding app startup time).
- **Classical invariant (N-constraint):** T-CLS-01 and T-CLS-02 must pass on every
  commit that touches `WindowConfig.py`, `FormOverlay.py`, or any `.ui.json` overlay.
- **Headless-safe:** The app may run in a headless environment with `QT_QPA_PLATFORM=offscreen`.
  The socket still works; `screenshot` falls back gracefully.

---

## 6. Implementation sequence

| Step | Deliverable |
|---|---|
| 1 | `tests/ui/client.py` — `CaissaClient` with retry logic |
| 2 | `tests/ui/conftest.py` — `caissa_proc`, `client`, `config_theme` fixtures |
| 3 | App-side `CAISSA_TEST=1` guard (suppress startup dialogs) |
| 4 | `tests/ui/test_overlay.py` — T-OVL-01 through T-OVL-08 |
| 5 | `tests/ui/test_classical.py` — T-CLS-01, T-CLS-02 |
| 6 | `pytest.ini` / `pyproject.toml` entry for `tests/ui` |

Steps 1-3 are the infrastructure; steps 4-5 are the tests that use it.

---

## 7. Out of scope

- Screenshot pixel-comparison ("golden image") tests — fragile across retina/non-retina and font-rendering differences; the widget-inspection approach is sufficient
- Windows / Linux CI — the socket server runs cross-platform but this machine is macOS-only
- Game-logic UI tests (move validation, engine output) — covered by the existing unit test suite and manual play testing

---

## References

- `bin/Code/Debug/RemoteControl.py` — socket server implementation
- `tools/caissa-ctl` — CLI client
- `docs/theme-mode-system.md` — overlay SDD being tested
