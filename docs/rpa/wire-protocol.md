# Wire Protocol

**Status:** Finalised against `bin/Code/Rpa/Service.py` (Phase 6).  
**See also:** `docs/rpa/quickstart.md` (end-to-end usage), `docs/rpa/cli.md` (CLI reference)

---

## Overview

The Caissa RPA layer adds 10 `rpa_*` verbs to the existing 25-verb RemoteControl Unix
socket protocol.  All verbs follow the same framing: send a newline-terminated command,
receive a JSON response.

```
echo 'rpa_state' | nc -U /tmp/caissa-control.sock
```

All `rpa_*` verbs accept a single JSON payload argument.  Verbs that take no parameters
accept an empty payload or no argument at all.

**Two invariants:**

1. **No blocking verb.** Every verb returns immediately; the run progresses on its own
   QTimer.  Waiting is client-side polling.
2. **Read-only verbs are always available.** `rpa_state`, `rpa_find`, `rpa_status`,
   `rpa_journal`, `rpa_capabilities`, `rpa_workflows` — these never actuate the UI and
   can be called at any time, including while a run is active.

---

## Concurrency Rule

At most one run may be in `RUNNING` or `PENDING` state at a time.  A second
`rpa_run`, `rpa_act`, or `rpa_converge` while one is active returns:

```json
{"error": "Run 'r-...' is already active (sub-state: CHECK_PRE). ...",
 "active_run_id": "r-20260828T142233-9f1c"}
```

`rpa_cancel` is **always** accepted — including during an active run.

---

## The 10 Verbs

### `rpa_capabilities`

Return CV/OCR availability flags.

**Request:**
```
rpa_capabilities
```

**Response:**
```json
{"cv_available": false, "ocr_available": false, "cv_version": null,
 "install_hint": "pip install -r requirements-rpa.txt  # then: brew install tesseract"}
```

---

### `rpa_state`

Return the current app state name and the first few recogniser widgets.

**Request:**
```
rpa_state
```

**Response:**
```json
{"state": "HOME", "widgets": [{"cls": "WBase", "visible": true}]}
```

**Possible state values:** `HOME`, `PLAYING`, `ENGINE_THINKING`, `GAME_OVER`,
`DIALOG_CONFIG`, `DIALOG_OTHER`, `MANAGER_OTHER`, `UNKNOWN`.

---

### `rpa_find`

Resolve a `Target` against the current snapshot and return matching elements.

**Request:**
```
rpa_find {"target": {"selector": {"cls": "QPushButton", "scope": "toolbar"}}}
```

**Response:**
```json
{"elements": [
  {"object_name": "TB_OPTIONS", "cls": "QPushButton", "text": "Options",
   "rect": [4, 4, 28, 28], "confidence": 0.6}
], "count": 1}
```

The `target` structure mirrors the `Target` dataclass: a `selector` dict (required),
and optional `anchor`, `direction`, `max_distance`, `timeout_ms`.  Selector fields are
documented in `docs/rpa/selectors.md`.

---

### `rpa_run`

Start a named workflow and return its `run_id`.

**Request:**
```
rpa_run {"workflow": "smoke_home"}
```

**Response (success):**
```json
{"run_id": "r-20260828T142233-9f1c"}
```

**Response (already active):**
```json
{"error": "Run 'r-...' is already active ...", "active_run_id": "r-..."}
```

**Response (unknown workflow):**
```json
{"error": "Workflow 'no_such_workflow' is not registered. Available: [...]"}
```

Use `rpa_status` to poll for completion.  There is no blocking `rpa_await`.

---

### `rpa_status`

Return the current status of a run.

**Request:**
```
rpa_status {"run_id": "r-20260828T142233-9f1c"}
```

**Response:**
```json
{"run_id": "r-20260828T142233-9f1c", "status": "RUNNING",
 "sub_state": "VERIFY", "total_pumps": 14, "active": true}
```

**Status values:** `PENDING`, `RUNNING`, `CANCELLING`, `SUCCEEDED`, `FAILED`,
`CANCELLED`, `TIMED_OUT`.

---

### `rpa_journal`

Return the full `RunRecord` for a completed (or in-progress) run.

**Request:**
```
rpa_journal {"run_id": "r-20260828T142233-9f1c"}
```

**Response:**
```json
{"journal": {
  "run_id": "r-20260828T142233-9f1c",
  "workflow_name": "smoke_home",
  "status": "SUCCEEDED",
  "created_at_ms": 1724850000000.0,
  "completed_at_ms": 1724850012345.0,
  "total_pumps": 47,
  "steps": [...],
  "error": null,
  "env": {"dpr": 2.0, "theme": "By default", "ui_mode": "classical",
          "cv_available": false, "ocr_available": false}
}}
```

For runs that have not yet completed, the `status` will be `RUNNING` and `completed_at_ms`
will be `null`.  If the run was not started in this process session, the journal is loaded
from `UserData/RpaRuns/<run_id>/journal.json`.

---

### `rpa_cancel`

Request cooperative cancellation of the active (or named) run.

**Request (cancel active run):**
```
rpa_cancel
```

**Request (cancel specific run):**
```
rpa_cancel {"run_id": "r-20260828T142233-9f1c"}
```

**Response:**
```json
{"ok": true, "run_id": "r-20260828T142233-9f1c"}
```

Cancellation is cooperative: the runner finishes the current actuation, runs compensation
for any completed steps, then terminates with `CANCELLED` status.  Use `rpa_status` to
confirm.

---

### `rpa_converge`

Start a convergence-only run to drive the app to a target state.  Returns a `run_id`
like `rpa_run`.

**Request:**
```
rpa_converge {"state": "HOME"}
```

**Response:**
```json
{"run_id": "r-20260828T142300-ab12"}
```

Useful for resetting the app to a known state before a workflow.

---

### `rpa_act`

Start a single-activity run.  Returns a `run_id` like `rpa_run`.

**Request:**
```
rpa_act {"activity": {"type": "OpenConfig"}}
```

**Request (Click):**
```
rpa_act {"activity": {"type": "Click", "selector": {"object_name": "TB_OPTIONS"}}}
```

**Response:**
```json
{"run_id": "r-20260828T142301-cd34"}
```

Supported activity types: `Click`, `TypeInto`, `SelectItem`, `GetText`, `ElementExists`,
`TakeScreenshot`, `OpenConfig`, `CloseDialog`, `SwitchTab`.

---

### `rpa_workflows`

List registered workflow names.

**Request:**
```
rpa_workflows
```

**Response:**
```json
{"workflows": ["classical_invariant", "config_roundtrip", "play_a_game", "smoke_home"]}
```

---

## `run_id` Scheme

`r-<yyyymmddThhmmss>-<4hex>` in UTC.  Example: `r-20260828T142233-9f1c`.

- Timestamp prefix makes journal retention (keep newest N) a plain directory sort.
- 4-hex suffix prevents collision if two runs start within the same second.
- IDs are generated by the service, not by the client — `FakeClock`-driven tests
  pass a deterministic ID directly to `Runner`.

---

## Timeout / Dispatch Interaction

Two timeout values that are NOT interchangeable:

| Context | Value | Meaning |
|---|---|---|
| `RemoteControl._handle_conn` `done.wait(timeout=15)` | 15 s | How long the socket thread waits for the Qt main thread to dispatch |
| `tests/ui/client.py` `_DEFAULT_TIMEOUT = 10.0` | 10 s | How long the test client waits for a socket response |

The client gives up first.  Both are documented here so nobody "fixes" one to match
the other.

---

## Kill Switch

Set `CAISSA_RPA=0` in the environment to disable the RPA layer entirely.  Every `rpa_*`
verb returns:

```json
{"error": "RPA layer disabled (CAISSA_RPA=0)"}
```

All 25 original verbs continue to work.  `Code.Rpa` is never imported.
