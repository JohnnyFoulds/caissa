# CLI Reference — `tools/caissa-rpa`

**Status:** Finalised against Phase 6.  
**See also:** `docs/rpa/wire-protocol.md` (raw verb reference), `docs/rpa/quickstart.md` (tutorial)

---

## Overview

`tools/caissa-rpa` is the run-oriented command-line client for the Caissa RPA layer.  It
wraps the `rpa_*` socket verbs with human-friendly output and polling.

For the raw 25-verb protocol, use `tools/caissa-ctl`.

**Prerequisites:** Caissa must be running (`tools/caissa`) and the socket must exist at
`/tmp/caissa-control.sock` (or `$CAISSA_SOCK`).

---

## Commands

### `state`

Print the current app state name.

```bash
tools/caissa-rpa state
# HOME
```

---

### `run <workflow> [--wait]`

Start a named workflow.  Without `--wait`, prints the `run_id` and returns immediately.
With `--wait`, polls until the run reaches a terminal state and prints the final status.

```bash
tools/caissa-rpa run smoke_home
# r-20260828T142233-9f1c

tools/caissa-rpa run smoke_home --wait
# {
#   "run_id": "r-20260828T142233-9f1c",
#   "status": "SUCCEEDED",
#   ...
# }
```

---

### `status <run_id>`

Print the current status of a run.

```bash
tools/caissa-rpa status r-20260828T142233-9f1c
# {
#   "run_id": "r-20260828T142233-9f1c",
#   "status": "RUNNING",
#   "sub_state": "VERIFY",
#   "total_pumps": 14,
#   "active": true
# }
```

---

### `journal <run_id>`

Print the full run journal as JSON.

```bash
tools/caissa-rpa journal r-20260828T142233-9f1c
```

---

### `find <selector_json>`

Resolve a selector against the live UI and print matching elements.

```bash
tools/caissa-rpa find '{"cls":"QPushButton","scope":"toolbar"}'
tools/caissa-rpa find '{"object_name":"TB_OPTIONS"}'
```

---

### `cancel [<run_id>]`

Cancel the active run (or a specific run by ID).

```bash
tools/caissa-rpa cancel
tools/caissa-rpa cancel r-20260828T142233-9f1c
```

---

### `workflows`

List registered workflow names.

```bash
tools/caissa-rpa workflows
# classical_invariant
# config_roundtrip
# play_a_game
# smoke_home
```

---

### `doctor`

Print a capability probe showing whether CV/OCR libraries are available.

```bash
tools/caissa-rpa doctor
# cv_available   : False
# ocr_available  : False
#
# install_hint: pip install -r requirements-rpa.txt  # then: brew install tesseract
```

---

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `CAISSA_SOCK` | `/tmp/caissa-control.sock` | Socket path |
| `CAISSA_RPA` | `1` | Set to `0` to disable the RPA layer entirely |

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Error (message on stderr) |
