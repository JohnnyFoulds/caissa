# Quickstart

Get the Caissa RPA layer running and execute your first workflow in under 5 minutes.

**Status:** Finalised against Phase 6.  
**See also:** `docs/rpa/cli.md` (CLI reference), `docs/rpa/concepts.md` (mental model)

---

## Prerequisites

- Python 3.13+, PySide6, Caissa installed and runnable via `tools/caissa`
- `nc` (netcat) for the socket examples below

Optional (for CV/OCR activities):
```bash
pip install -r requirements-rpa.txt   # opencv-python-headless + pytesseract
brew install tesseract                 # macOS — Linux: apt install tesseract-ocr
```

---

## Step 1 — Start Caissa

```bash
nohup tools/caissa > /tmp/caissa.log 2>&1 &
```

Wait until the main window appears (about 5 seconds).

---

## Step 2 — Verify the socket is alive

```bash
echo 'ping' | nc -U /tmp/caissa-control.sock
# {"ok": true}
```

---

## Step 3 — Check RPA capabilities

```bash
tools/caissa-rpa doctor
```

Expected output (without CV/OCR):
```
cv_available   : False
ocr_available  : False

install_hint: pip install -r requirements-rpa.txt  # then: brew install tesseract
```

The object-tier RPA layer works fully without CV/OCR.

---

## Step 4 — Inspect the current app state

```bash
tools/caissa-rpa state
# HOME
```

---

## Step 5 — Find a widget

```bash
tools/caissa-rpa find '{"object_name": "TB_OPTIONS"}'
```

Expected output:
```json
{
  "elements": [
    {"object_name": "TB_OPTIONS", "cls": "QPushButton",
     "text": "Options", "rect": [4, 4, 28, 28], "confidence": 1.0}
  ],
  "count": 1
}
```

If `count` is 0, the toolbar is hidden or the app is not at HOME state.

---

## Step 6 — Run a single activity

```bash
SOCK=/tmp/caissa-control.sock

# Start a single OpenConfig activity (opens the Configuration dialog)
RUN=$(echo 'rpa_act {"activity":{"type":"OpenConfig"}}' \
      | nc -U $SOCK \
      | python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["run_id"])')

echo "Run started: $RUN"

# Poll until complete (typically < 1 second)
for i in $(seq 1 20); do
  STATUS=$(echo "rpa_status {\"run_id\":\"$RUN\"}" | nc -U $SOCK)
  echo "$STATUS" | python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print(d["status"])'
  DONE=$(echo "$STATUS" | python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print(d["status"] in ["SUCCEEDED","FAILED","CANCELLED","TIMED_OUT"])')
  [ "$DONE" = "True" ] && break
  sleep 0.25
done

# Close the dialog
echo 'dialog_cancel' | nc -U $SOCK
```

---

## Step 7 — Read the journal

```bash
tools/caissa-rpa journal $RUN
```

The journal shows every pump, sub-state trace, and the `env` block capturing the
runtime context at run start.

---

## Step 8 — Run a workflow (Phase 8 and later)

Once workflows are registered (Phase 8):

```bash
tools/caissa-rpa run smoke_home --wait
tools/caissa-rpa run classical_invariant --wait
```

Or use the Python client:

```python
from tests.ui.rpa_client import CaissaRpaClient

rpa = CaissaRpaClient()
stat = rpa.run_and_wait("smoke_home", timeout=30.0)
print(stat["status"])  # SUCCEEDED
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `socket not found` | Caissa not running | `tools/caissa &` |
| `{"error": "RPA layer disabled"}` | `CAISSA_RPA=0` in env | `unset CAISSA_RPA` |
| `Workflow 'X' is not registered` | Workflow not yet shipped | Phase 8 adds workflows |
| `RunAlreadyActiveError` | Previous run still active | `tools/caissa-rpa cancel` |
| `rpa_find` returns `count: 0` | App not at expected state | `tools/caissa-rpa state` |

See `docs/rpa/troubleshooting.md` for a full symptom → cause → fix table.
