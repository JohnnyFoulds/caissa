# Creating an RPA Layer for a New Target Application

**Audience:** A developer (or Claude Code session) that needs to automate a new external
application — FS-UAE, a DOS emulator, a desktop GUI, a browser — using the Caissa RPA
Activity pattern.

**Prerequisite reading:** `docs/rpa/uipath-mapping.md` (vocabulary),
`docs/rpa/state-machine.md` (runner contract),
`bin/Code/Dos/Activities.py` (the reference implementation).

---

## The Principle

In UiPath you do not write VBA to click a button. You add a `Click` activity to a Sequence,
set its selector, test it, then wire it into the flow. The same rule applies here:

> **Any interaction with a running process = an `Activity` subclass.**

An Activity is verifiable, retryable, testable without the running application, and
survives context compaction (it lives in the codebase, not in a `/tmp` script).

---

## Step 1 — Create the Driver

The driver is the boundary between Python and the OS/application. It has exactly three
responsibilities: take screenshots, send input events, and identify the window.

Create `bin/Code/<Target>/Driver.py`. It is a plain class — no base class required.

**Minimum surface:**

```python
class TargetDriver:
    def __init__(self): ...
    def screenshot(self) -> PIL.Image.Image: ...   # current window pixels
    def focus(self) -> None: ...                   # bring window to front
    def click(self, x: int, y: int) -> None: ...   # window-relative left click
    def mousedown(self, x: int, y: int) -> None: ...
    def mouseup(self, x: int, y: int) -> None: ...
    def key(self, keycode: int) -> None: ...       # OS key code
    @property
    def window_id(self) -> int: ...                # Quartz window ID (macOS)
```

**macOS pattern (Quartz):**

```python
import subprocess, Quartz

def _find_window_id(title_fragment: str) -> int | None:
    wins = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
    )
    for w in wins:
        if title_fragment.lower() in (w.get("kCGWindowOwnerName") or "").lower():
            return w["kCGWindowNumber"]
    return None

def screenshot(self) -> PIL.Image.Image:
    wid = self.window_id
    result = subprocess.run(
        ["screencapture", "-x", "-o", "-l", str(wid), "-t", "png", "/tmp/_rpa_shot.png"],
        capture_output=True,
    )
    return PIL.Image.open("/tmp/_rpa_shot.png").copy()

def focus(self) -> None:
    # CGWindowListCopyWindowInfo → kCGWindowOwnerPID → NSRunningApplication.activateWithOptions
    ...
```

See `bin/Code/Dos/Driver.py` for the full reference implementation including Quartz mouse and
keyboard event posting.

**Key rule:** the driver MUST be callable without the target application running (for import-
time tests). All I/O happens inside methods, never at module level.

---

## Step 2 — Define AppStates (optional but recommended)

An `AppState` is an observable, screenshot-detectable state of the application.

```python
from enum import Enum

class AmigaState(Enum):
    UNKNOWN    = "unknown"
    LAUNCHING  = "launching"   # process running, no window yet
    TITLE      = "title"       # title screen / intro animation
    MENU       = "menu"        # main game menu
    BOARD      = "board"       # chess board visible
    THINKING   = "thinking"    # computer is thinking (if detectable)

def recognise(img: PIL.Image.Image) -> AmigaState:
    """Detect current state from a screenshot."""
    # Use colour fraction, template match, or OCR.
    # Must be fast (called on every CHECK_PRE).
    ...
```

AppState is used in `precondition()` to guard an activity, and in `postcondition()` to
confirm a transition.

---

## Step 3 — Create Activities

Each distinct UI interaction is one `Activity` subclass in `bin/Code/<Target>/Activities.py`.

**The contract (identical to UiPath):**

```
precondition() → True?
    NO  → runner converges to required_state, then retries
    YES → execute() fires once → settle_ms elapses → postcondition() polled
              postcondition() → True?  → step succeeds, move to next activity
              postcondition() → False? → DECIDE_RECOVERY (retry / compensate / unwind)
```

**Template:**

```python
class WaitForBoard(TargetActivity):
    """Wait until the chess board is visible on screen.

    precondition: always True — we are only waiting.
    execute: no-op.
    postcondition: board colour signature detected (polled until verify_ms).
    """
    name = "WaitForBoard"
    check_pre_screenshot = False   # precondition needs no image
    verify_screenshot = True
    settle_ms = 0
    verify_ms = 30_000             # 30 s for cold launch

    def precondition(self, img, ctx):
        return True

    def execute(self, driver, ctx):
        pass                       # polling only; runner does the wait

    def postcondition(self, img, ctx):
        return _board_visible(img)
```

**Rules:**
- `execute()` issues **one** driver action and returns immediately. Never loop in execute().
  Never `time.sleep()` in execute(). Waiting is `settle_ms` + the VERIFY polling loop.
- `precondition()` must be fast (called on every CHECK_PRE pump, possibly hundreds of times).
- `postcondition()` must be idempotent and side-effect-free (called many times during VERIFY).
- `settle_ms` is the minimum time after execute before postcondition is first called.
  Set it to the shortest animation time the action triggers.
- `verify_ms` is the maximum time postcondition is polled. Set it to the maximum realistic
  completion time, not a guess. Overshoot is fine; it just means a longer timeout.

**Naming conventions (UiPath analogy):**

| Pattern | Activity name | UiPath analogue |
|---|---|---|
| Ensure something is running | `EnsureXRunning` | Invoke Application |
| Wait for a state without acting | `WaitForX` | Element Exists (polling) |
| Navigate to a state | `NavigateTo(state)` | Click + wait |
| Perform a game action | `PlayMove`, `SelectLevel` | Click, Type Into |
| Extract output | `ExtractX` | Get Text, Data Scraping |

---

## Step 4 — Write unit tests with FakeDriver

Tests MUST NOT require the real application. A `FakeDriver` replays pre-captured PIL images.

```python
# tests/unit/<target>/test_activities.py

class FakeDriver:
    """Returns images from a queue; records calls to execute() side effects."""
    def __init__(self, images: list[PIL.Image.Image]):
        self._images = list(images)
        self.clicked: list[tuple[int,int]] = []

    def screenshot(self) -> PIL.Image.Image:
        return self._images.pop(0)

    def click(self, x, y):
        self.clicked.append((x, y))

    def focus(self): pass


def test_wait_for_board_precondition_always_true():
    act = WaitForBoard()
    assert act.precondition(None, {}) is True


def test_wait_for_board_postcondition_true_on_board_image():
    img = PIL.Image.open("tests/fixtures/amiga/board_visible.png")
    act = WaitForBoard()
    assert act.postcondition(img, {}) is True


def test_wait_for_board_postcondition_false_on_title_image():
    img = PIL.Image.open("tests/fixtures/amiga/title_screen.png")
    act = WaitForBoard()
    assert act.postcondition(img, {}) is False
```

**Fixture images:** capture a real screenshot from the application in each relevant state,
save to `tests/fixtures/<target>/`. Commit these images — they are the ground truth for
the precondition/postcondition logic.

**What to test for each activity:**
1. `precondition()` returns True when the app is in the correct state
2. `precondition()` returns False when the app is in the wrong state
3. `postcondition()` returns True after a successful execute
4. `postcondition()` returns False before execute (to confirm the base case)

---

## Step 5 — Calibration

Before writing pixel logic, boot the real application and take a screenshot.

```python
# One-shot calibration helper (not committed to production code)
from Code.<Target>.Driver import TargetDriver
d = TargetDriver()
img = d.screenshot()
img.save("UserData/<Target>/calibration.png")
# Open calibration.png in Preview; use the pixel inspector to measure coordinates
```

Record what you measure in two places **immediately**:
1. `bin/Code/<Target>/BattleChess.py` as named constants
2. This CLAUDE.md under the `## <Target> Automation Layer` section

Never leave measured values only in a variable in a running Python session.
Never note them in a `/tmp` file. Context compaction will destroy that knowledge.

---

## Step 6 — Wire into a Runner

```python
from Code.<Target>.Driver import TargetDriver
from Code.<Target>.Activities import (
    EnsureXRunning, WaitForBoard, PlayMove, WaitForReply, ExtractMove
)
from Code.<Target>.Activities import TargetRunner

driver = TargetDriver()
activities = [
    EnsureXRunning(config_path="..."),
    WaitForBoard(),
    PlayMove("e2", "e4"),
    WaitForReply(),
    ExtractMove(),
]
ctx = TargetRunner().run(driver, activities)
print(ctx["computer_move"])
```

The runner handles settle/verify/retry. You provide the list of Activities and the driver.

---

## Reference implementation

`bin/Code/Dos/` is the canonical reference. Every Activity pattern, Driver structure, and
FakeDriver test pattern in that directory applies verbatim to any new target.

Activities ported so far:
- `bin/Code/Dos/Activities.py` — Battle Chess via DOSBox-X (complete; corpus recording works)
- `bin/Code/Amiga/Activities.py` — Battle Chess via FS-UAE (in progress — Phase E)
